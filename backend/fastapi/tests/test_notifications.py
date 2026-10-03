import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import models
from auth import create_access_token
from database import Base

main.engine.echo = False


class NotificationApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        db = self.Session()
        self.owner = models.User(
            name="Notification Owner",
            email="notification-owner@example.invalid",
            password_hash="unused",
            role="customer",
            is_active=True
        )
        self.other_user = models.User(
            name="Notification Other",
            email="notification-other@example.invalid",
            password_hash="unused",
            role="customer",
            is_active=True
        )
        db.add_all([self.owner, self.other_user])
        db.flush()
        self.product = models.Product(
            name="Notification Test Product",
            category="Test",
            price=Decimal("10.00"),
            stock=10,
            is_active=True
        )
        db.add(self.product)
        db.flush()
        self.order = self._make_order(db, self.owner.id)
        db.commit()
        self.owner_id = self.owner.id
        self.other_user_id = self.other_user.id
        self.order_id = self.order.id
        product_id = self.product.id
        db.close()
        self.product_id = product_id

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        main.app.dependency_overrides[main.get_db] = override_get_db
        self.client = TestClient(main.app)
        self.owner_headers = self._headers(self.owner_id, "customer")
        self.other_headers = self._headers(self.other_user_id, "customer")
        self.admin_headers = self._headers(self.owner_id, "admin")
        self.staff_headers = self._headers(self.owner_id, "staff")
        self.env_patcher = patch.dict(
            os.environ,
            {"STRIPE_WEBHOOK_SECRET": "whsec_notification_test"}
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        main.app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    @staticmethod
    def _headers(user_id, role):
        token = create_access_token({"sub": str(user_id), "role": role})
        return {"Authorization": f"Bearer {token}"}

    def _make_order(self, db, user_id):
        order = models.Order(
            user_id=user_id,
            total_amount=Decimal("20.00"),
            status="PENDING",
            stock_restored=False
        )
        db.add(order)
        db.flush()
        db.add(models.OrderItem(
            order_id=order.id,
            product_id=self.product.id,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            subtotal=Decimal("20.00")
        ))
        db.flush()
        return order

    def _create_notification(
        self,
        *,
        user_id=None,
        notification_type="ORDER_CREATED",
        title="Order placed",
        message="Your order was placed.",
        is_read=False,
        event_key=None
    ):
        db = self.Session()
        try:
            notification = models.Notification(
                user_id=user_id or self.owner_id,
                title=title,
                message=message,
                notification_type=notification_type,
                is_read=is_read,
                event_key=event_key
            )
            db.add(notification)
            db.commit()
            db.refresh(notification)
            return notification.id
        finally:
            db.close()

    def _notification_count(self, user_id=None):
        db = self.Session()
        try:
            query = db.query(models.Notification)
            if user_id is not None:
                query = query.filter(models.Notification.user_id == user_id)
            return query.count()
        finally:
            db.close()

    def _webhook(self, event_id, event_type, intent_id):
        event_data = {
            "id": event_id,
            "type": event_type,
            "data": {"object": {"id": intent_id}}
        }
        with patch("main.construct_webhook_event", return_value=event_data):
            return self.client.post(
                "/payments/webhook",
                content=b"verified by mocked Stripe constructor",
                headers={"Stripe-Signature": "test-signature"}
            )

    def test_create_and_list_only_owner_notifications(self):
        owner_id = self._create_notification()
        self._create_notification(user_id=self.other_user_id)

        owner_list = self.client.get(
            "/notifications",
            headers=self.owner_headers
        )
        other_list = self.client.get(
            "/notifications",
            headers=self.other_headers
        )

        self.assertEqual(owner_list.status_code, 200)
        self.assertEqual(len(owner_list.json()), 1)
        self.assertEqual(owner_list.json()[0]["id"], owner_id)
        self.assertEqual(owner_list.json()[0]["user_id"], self.owner_id)
        self.assertEqual(len(other_list.json()), 1)
        self.assertNotEqual(other_list.json()[0]["id"], owner_id)

    def test_read_filter_pagination_and_newest_first(self):
        older_id = self._create_notification(message="older")
        newer_id = self._create_notification(message="newer")
        read_id = self._create_notification(message="read", is_read=True)

        unread = self.client.get(
            "/notifications?is_read=false&limit=1&offset=0",
            headers=self.owner_headers
        )
        read = self.client.get(
            "/notifications?is_read=true",
            headers=self.owner_headers
        )
        newest = self.client.get(
            "/notifications?limit=1",
            headers=self.owner_headers
        )

        self.assertEqual([item["id"] for item in unread.json()], [newer_id])
        self.assertEqual(len(read.json()), 1)
        self.assertEqual(newest.json()[0]["id"], read_id)
        self.assertNotEqual(older_id, newer_id)

    def test_unread_count_and_mark_single_read(self):
        notification_id = self._create_notification()
        self._create_notification(is_read=True)

        count = self.client.get(
            "/notifications/unread-count",
            headers=self.owner_headers
        )
        marked = self.client.put(
            f"/notifications/{notification_id}/read",
            headers=self.owner_headers
        )
        new_count = self.client.get(
            "/notifications/unread-count",
            headers=self.owner_headers
        )

        self.assertEqual(count.json(), {"unread_count": 1})
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.json()["is_read"])
        self.assertEqual(new_count.json(), {"unread_count": 0})

    def test_users_cannot_mark_another_users_notification(self):
        notification_id = self._create_notification(user_id=self.owner_id)

        response = self.client.put(
            f"/notifications/{notification_id}/read",
            headers=self.other_headers
        )

        self.assertEqual(response.status_code, 404)

    def test_mark_all_read_is_scoped_to_current_user(self):
        self._create_notification()
        self._create_notification()
        other_id = self._create_notification(user_id=self.other_user_id)

        response = self.client.put(
            "/notifications/read-all",
            headers=self.owner_headers
        )
        owner_count = self.client.get(
            "/notifications/unread-count",
            headers=self.owner_headers
        ).json()["unread_count"]
        other_unread = self.client.get(
            "/notifications/unread-count",
            headers=self.other_headers
        ).json()["unread_count"]
        db = self.Session()
        try:
            self.assertFalse(db.query(models.Notification).filter_by(
                id=other_id
            ).one().is_read)
        finally:
            db.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated_count"], 2)
        self.assertEqual(owner_count, 0)
        self.assertEqual(other_unread, 1)

    def test_order_creation_creates_order_notification(self):
        db = self.Session()
        db.add(models.Cart(
            user_id=self.owner_id,
            product_id=self.product_id,
            quantity=1
        ))
        db.commit()
        db.close()

        response = self.client.post("/orders", headers=self.owner_headers)
        notifications = self.client.get(
            "/notifications",
            headers=self.owner_headers
        ).json()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["title"], "Order placed")
        self.assertEqual(
            notifications[0]["message"],
            f"Your order #{response.json()['id']} has been placed successfully."
        )
        self.assertEqual(notifications[0]["notification_type"], "ORDER_CREATED")

    def test_payment_success_webhook_creates_one_notification(self):
        payment_id = self._insert_payment("pi_notice_success")

        first = self._webhook(
            "evt_payment_success",
            "payment_intent.succeeded",
            "pi_notice_success"
        )
        repeated = self._webhook(
            "evt_payment_success",
            "payment_intent.succeeded",
            "pi_notice_success"
        )
        notifications = self.client.get(
            "/notifications",
            headers=self.owner_headers
        ).json()
        db = self.Session()
        try:
            payment = db.query(models.Payment).filter_by(id=payment_id).one()
            order = db.query(models.Order).filter_by(id=self.order_id).one()
            self.assertEqual(payment.status, "SUCCEEDED")
            self.assertEqual(order.status, "CONFIRMED")
        finally:
            db.close()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["title"], "Payment successful")
        self.assertEqual(notifications[0]["notification_type"], "PAYMENT_SUCCESS")

    def test_payment_failure_webhook_creates_notification_without_confirming(self):
        self._insert_payment("pi_notice_failure")

        response = self._webhook(
            "evt_payment_failure",
            "payment_intent.payment_failed",
            "pi_notice_failure"
        )
        notifications = self.client.get(
            "/notifications",
            headers=self.owner_headers
        ).json()
        db = self.Session()
        try:
            order = db.query(models.Order).filter_by(id=self.order_id).one()
            payment = db.query(models.Payment).one()
            self.assertEqual(payment.status, "FAILED")
            self.assertEqual(order.status, "PENDING")
        finally:
            db.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["title"], "Payment failed")
        self.assertEqual(notifications[0]["notification_type"], "PAYMENT_FAILED")

    def test_admin_status_change_creates_notification_once(self):
        payload = {"status": "PROCESSING"}
        first = self.client.put(
            f"/admin/orders/{self.order_id}/status",
            json=payload,
            headers=self.admin_headers
        )
        repeated = self.client.put(
            f"/admin/orders/{self.order_id}/status",
            json=payload,
            headers=self.admin_headers
        )
        notifications = self.client.get(
            "/notifications",
            headers=self.owner_headers
        ).json()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["notification_type"], "ORDER_PROCESSING")
        self.assertEqual(
            notifications[0]["message"],
            f"Your order #{self.order_id} is now being processed."
        )

    def test_admin_and_staff_can_view_notifications_but_customer_cannot(self):
        self._create_notification()

        denied = self.client.get(
            "/admin/notifications",
            headers=self.owner_headers
        )
        admin = self.client.get(
            "/admin/notifications?user_id=" + str(self.owner_id),
            headers=self.admin_headers
        )
        staff = self.client.get(
            "/admin/notifications",
            headers=self.staff_headers
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(admin.status_code, 200)
        self.assertEqual(staff.status_code, 200)
        self.assertEqual(admin.json()[0]["user_id"], self.owner_id)

    def test_invalid_id_and_unauthorized_requests(self):
        self.assertEqual(
            self.client.get("/notifications").status_code,
            401
        )
        self.assertEqual(
            self.client.get(
                "/notifications",
                headers={"Authorization": "Bearer malformed-test-token"}
            ).status_code,
            401
        )
        self.assertEqual(
            self.client.put("/notifications/read-all").status_code,
            401
        )
        self.assertEqual(
            self.client.put(
                "/notifications/999999/read",
                headers=self.owner_headers
            ).status_code,
            404
        )

    def test_auth0_exchange_creates_verified_customer_and_local_token(self):
        claims = {
            "email": "social-customer@example.invalid",
            "email_verified": True,
            "name": "Social Customer",
        }
        with patch("main.verify_auth0_id_token", return_value=claims):
            response = self.client.post(
                "/auth0-exchange",
            json={"id_token": "verified-auth0-token"}
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["role"], "customer")
        profile = self.client.get(
            "/profile",
            headers={"Authorization": f"Bearer {data['access_token']}"}
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["role"], "customer")

        db = self.Session()
        try:
            user = db.query(models.User).filter_by(
                email="social-customer@example.invalid"
            ).one()
            self.assertEqual(user.role, "customer")
            self.assertTrue(user.is_active)
            self.assertNotEqual(user.password_hash, "")
        finally:
            db.close()

    def test_auth0_exchange_links_existing_user_without_privilege_escalation(self):
        db = self.Session()
        try:
            self.owner.role = "admin"
            db.merge(self.owner)
            db.commit()
        finally:
            db.close()

        claims = {
            "email": self.owner.email,
            "email_verified": True,
            "name": "Updated Auth0 Name",
        }
        with patch("main.verify_auth0_id_token", return_value=claims):
            response = self.client.post(
                "/auth0-exchange",
            json={"id_token": "verified-auth0-token"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], self.owner_id)
        self.assertEqual(response.json()["role"], "customer")
        denied = self.client.get(
            "/admin/test",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"}
        )
        self.assertEqual(denied.status_code, 403)

    def test_auth0_exchange_rejects_invalid_or_unverified_identity(self):
        body = {"id_token": "auth0-token"}
        with patch("main.verify_auth0_id_token", return_value=None):
            invalid = self.client.post("/auth0-exchange", json=body)
        with patch("main.verify_auth0_id_token", return_value={
            "email": "unverified@example.invalid",
            "email_verified": False,
        }):
            unverified = self.client.post("/auth0-exchange", json=body)

        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(unverified.status_code, 403)

    def test_database_notification_has_required_content_and_default_unread(self):
        notification_id = self._create_notification(
            title="Payment successful",
            message="Payment completed safely.",
            notification_type="PAYMENT_SUCCESS"
        )
        db = self.Session()
        try:
            notification = db.query(models.Notification).filter_by(
                id=notification_id
            ).one()
            self.assertTrue(notification.title)
            self.assertTrue(notification.message)
            self.assertEqual(notification.notification_type, "PAYMENT_SUCCESS")
            self.assertFalse(notification.is_read)
            self.assertIsNotNone(notification.created_at)
        finally:
            db.close()

    def _insert_payment(self, intent_id):
        db = self.Session()
        try:
            payment = models.Payment(
                order_id=self.order_id,
                user_id=self.owner_id,
                amount=Decimal("20.00"),
                currency="inr",
                status="PENDING",
                stripe_payment_intent_id=intent_id
            )
            db.add(payment)
            db.commit()
            db.refresh(payment)
            return payment.id
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
