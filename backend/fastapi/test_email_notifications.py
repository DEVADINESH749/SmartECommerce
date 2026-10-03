import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import email_service
import main
import models
from auth import create_access_token
from database import Base
from email_templates import (
    order_cancelled_email,
    order_created_email,
    order_delivered_email,
    order_processing_email,
    order_shipped_email,
    payment_failed_email,
    payment_success_email,
)

main.engine.echo = False


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.smtp_values = {
            "SMTP_HOST": "smtp.example.invalid",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "mailer@example.invalid",
            "SMTP_PASSWORD": "unit-test-not-a-real-password",
            "SMTP_FROM_EMAIL": "shop@example.invalid",
            "SMTP_FROM_NAME": "Smart E-Commerce",
            "SMTP_USE_TLS": "true"
        }

    def test_smtp_configuration_and_message_are_loaded(self):
        with patch.dict(os.environ, self.smtp_values, clear=False):
            with patch("email_service.smtplib.SMTP") as smtp_factory:
                server = smtp_factory.return_value.__enter__.return_value
                email_service.send_email(
                    "customer@example.invalid",
                    "Test subject",
                    "<p>HTML body</p>",
                    "Plain body"
                )

        smtp_factory.assert_called_once_with(
            "smtp.example.invalid",
            587,
            timeout=15
        )
        server.starttls.assert_called_once()
        server.login.assert_called_once_with(
            "mailer@example.invalid",
            self.smtp_values["SMTP_PASSWORD"]
        )
        message = server.send_message.call_args.args[0]
        self.assertEqual(message["To"], "customer@example.invalid")
        self.assertEqual(message["Subject"], "Test subject")
        self.assertIn("Plain body", message.get_body(preferencelist=("plain",)).get_content())
        self.assertIn("HTML body", message.get_body(preferencelist=("html",)).get_content())

    def test_missing_smtp_configuration_is_controlled(self):
        empty_settings = {
            key: "" for key in (
                "SMTP_HOST",
                "SMTP_USERNAME",
                "SMTP_PASSWORD",
                "SMTP_FROM_EMAIL"
            )
        }
        with patch.dict(os.environ, empty_settings, clear=False):
            with self.assertRaises(email_service.EmailConfigurationError):
                email_service.send_email(
                    "customer@example.invalid",
                    "Subject",
                    "<p>Body</p>",
                    "Body"
                )

    def test_smtp_failure_is_sanitized(self):
        with patch.dict(os.environ, self.smtp_values, clear=False):
            with patch("email_service.smtplib.SMTP") as smtp_factory:
                server = smtp_factory.return_value.__enter__.return_value
                server.send_message.side_effect = OSError("private transport detail")
                with self.assertRaises(email_service.EmailDeliveryError) as raised:
                    email_service.send_email(
                        "customer@example.invalid",
                        "Subject",
                        "<p>Body</p>",
                        "Body"
                    )

        self.assertNotIn(self.smtp_values["SMTP_PASSWORD"], str(raised.exception))
        self.assertNotIn("private transport detail", str(raised.exception))

    def test_all_templates_include_text_and_html_without_sensitive_data(self):
        templates = [
            order_created_email("Customer", 5, Decimal("599.00")),
            payment_success_email("Customer", 5, Decimal("599.00")),
            payment_failed_email("Customer", 5, Decimal("599.00")),
            order_processing_email("Customer", 5),
            order_shipped_email("Customer", 5),
            order_delivered_email("Customer", 5),
            order_cancelled_email("Customer", 5),
        ]
        all_content = " ".join(
            template["subject"] + template["html"] + template["text"]
            for template in templates
        ).lower()

        self.assertTrue(all({"subject", "html", "text"} <= template.keys()
                            for template in templates))
        self.assertIn("₹599.00", templates[0]["text"])
        self.assertNotIn("password", all_content)
        self.assertNotIn("cvv", all_content)
        self.assertNotIn("card number", all_content)
        self.assertNotIn("client_secret", all_content)
        self.assertNotIn("sk_test", all_content)


class EmailBusinessEventTests(unittest.TestCase):
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
        self.user = models.User(
            name="Email Customer",
            email="email-customer@example.invalid",
            password_hash="unused",
            role="customer",
            is_active=True
        )
        db.add(self.user)
        db.flush()
        self.product = models.Product(
            name="Email Test Product",
            category="Test",
            price=Decimal("10.00"),
            stock=10,
            is_active=True
        )
        db.add(self.product)
        db.flush()
        self.order = self._create_order(db, self.user.id)
        db.commit()
        self.user_id = self.user.id
        self.order_id = self.order.id
        self.product_id = self.product.id
        db.close()

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        main.app.dependency_overrides[main.get_db] = override_get_db
        self.client = TestClient(main.app)
        token = create_access_token({"sub": str(self.user_id), "role": "customer"})
        self.customer_headers = {"Authorization": f"Bearer {token}"}
        admin_token = create_access_token({"sub": str(self.user_id), "role": "admin"})
        self.admin_headers = {"Authorization": f"Bearer {admin_token}"}
        self.smtp_env = patch.dict(
            os.environ,
            {"SMTP_WEBHOOK_TEST": "true", "STRIPE_WEBHOOK_SECRET": "whsec_email_test"},
            clear=False
        )
        self.smtp_env.start()

    def tearDown(self):
        self.smtp_env.stop()
        main.app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def _create_order(self, db, user_id):
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

    def _insert_payment(self, intent_id):
        db = self.Session()
        try:
            payment = models.Payment(
                order_id=self.order_id,
                user_id=self.user_id,
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

    def _webhook(self, event_id, event_type, intent_id):
        event = {
            "id": event_id,
            "type": event_type,
            "data": {"object": {"id": intent_id}}
        }
        with patch("main.construct_webhook_event", return_value=event):
            return self.client.post(
                "/payments/webhook",
                content=b"verified event",
                headers={"Stripe-Signature": "mocked-signature"}
            )

    def _notification_types(self):
        db = self.Session()
        try:
            return [item.notification_type for item in db.query(
                models.Notification
            ).filter_by(user_id=self.user_id).all()]
        finally:
            db.close()

    def _order_status(self):
        db = self.Session()
        try:
            return db.query(models.Order).filter_by(id=self.order_id).one().status
        finally:
            db.close()

    def test_order_created_email_and_notification_survive_delivery_failure(self):
        db = self.Session()
        db.add(models.Cart(
            user_id=self.user_id,
            product_id=self.product_id,
            quantity=1
        ))
        db.commit()
        db.close()

        with patch("main.send_email", side_effect=email_service.EmailDeliveryError):
            response = self.client.post("/orders", headers=self.customer_headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self._notification_types(), ["ORDER_CREATED"])
        db = self.Session()
        try:
            self.assertIsNotNone(db.query(models.Order).filter_by(
                user_id=self.user_id
            ).first())
        finally:
            db.close()

    @patch("main.send_email")
    def test_order_created_email_content(self, send):
        db = self.Session()
        db.add(models.Cart(
            user_id=self.user_id,
            product_id=self.product_id,
            quantity=1
        ))
        db.commit()
        db.close()

        response = self.client.post("/orders", headers=self.customer_headers)

        self.assertEqual(response.status_code, 201)
        template = send.call_args.kwargs
        self.assertIn(f"Order #{response.json()['id']}", template["subject"])
        self.assertIn("Order total: ₹10.00", template["text_body"])

    def test_payment_success_email_is_sent_once_after_commit(self):
        self._insert_payment("pi_email_success")

        with patch("main.send_email") as send:
            first = self._webhook(
                "evt_email_success",
                "payment_intent.succeeded",
                "pi_email_success"
            )
            repeated = self._webhook(
                "evt_email_success",
                "payment_intent.succeeded",
                "pi_email_success"
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        send.assert_called_once()
        self.assertIn("Payment Successful", send.call_args.kwargs["subject"])
        self.assertEqual(self._order_status(), "CONFIRMED")
        self.assertIn("PAYMENT_SUCCESS", self._notification_types())

    def test_payment_failure_email_keeps_order_pending(self):
        self._insert_payment("pi_email_failed")

        with patch("main.send_email") as send:
            response = self._webhook(
                "evt_email_failed",
                "payment_intent.payment_failed",
                "pi_email_failed"
            )

        self.assertEqual(response.status_code, 200)
        send.assert_called_once()
        self.assertIn("Payment Failed", send.call_args.kwargs["subject"])
        self.assertEqual(self._order_status(), "PENDING")
        self.assertIn("PAYMENT_FAILED", self._notification_types())

    def test_payment_email_failure_does_not_undo_success(self):
        self._insert_payment("pi_email_send_failure")

        with patch("main.send_email", side_effect=RuntimeError("safe mock failure")):
            response = self._webhook(
                "evt_email_send_failure",
                "payment_intent.succeeded",
                "pi_email_send_failure"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._order_status(), "CONFIRMED")
        self.assertIn("PAYMENT_SUCCESS", self._notification_types())

    def test_changed_status_emails_send_once_and_unchanged_status_does_not(self):
        with patch("main.send_email") as send:
            processing = {"status": "PROCESSING"}
            first = self.client.put(
                f"/admin/orders/{self.order_id}/status",
                json=processing,
                headers=self.admin_headers
            )
            repeated = self.client.put(
                f"/admin/orders/{self.order_id}/status",
                json=processing,
                headers=self.admin_headers
            )
            shipped = self.client.put(
                f"/admin/orders/{self.order_id}/status",
                json={"status": "SHIPPED"},
                headers=self.admin_headers
            )
            delivered = self.client.put(
                f"/admin/orders/{self.order_id}/status",
                json={"status": "DELIVERED"},
                headers=self.admin_headers
            )
            cancelled = self.client.put(
                f"/admin/orders/{self.order_id}/status",
                json={"status": "CANCELLED"},
                headers=self.admin_headers
            )

        self.assertTrue(all(
            response.status_code == 200
            for response in (first, repeated, shipped, delivered, cancelled)
        ))
        self.assertEqual(send.call_count, 4)
        self.assertIn("Being Processed", send.call_args_list[0].kwargs["subject"])
        self.assertIn("Shipped", send.call_args_list[1].kwargs["subject"])
        self.assertIn("Delivered", send.call_args_list[2].kwargs["subject"])
        self.assertIn("Cancelled", send.call_args_list[3].kwargs["subject"])

    def test_customer_cancellation_sends_cancelled_email(self):
        with patch("main.send_email") as send:
            response = self.client.post(
                f"/orders/{self.order_id}/cancel",
                headers=self.customer_headers
            )

        self.assertEqual(response.status_code, 200)
        send.assert_called_once()
        self.assertIn("Cancelled", send.call_args.kwargs["subject"])


if __name__ == "__main__":
    unittest.main()
