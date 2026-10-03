import hashlib
import hmac
import json
import os
import time
import unittest
from decimal import Decimal
from pathlib import Path
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


class PaymentApiTests(unittest.TestCase):
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
        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False
        )
        self.db = self.Session()
        self.owner = models.User(
            name="Payment Owner",
            email="payment-owner@example.invalid",
            password_hash="unused",
            role="customer",
            is_active=True
        )
        self.other_user = models.User(
            name="Other Customer",
            email="other-customer@example.invalid",
            password_hash="unused",
            role="customer",
            is_active=True
        )
        self.db.add_all([self.owner, self.other_user])
        self.db.flush()
        self.product = models.Product(
            name="Payment Test Product",
            category="Test",
            price=Decimal("12.34"),
            stock=5,
            is_active=True
        )
        self.db.add(self.product)
        self.db.flush()
        self.order = self._make_order(self.owner.id)
        self.other_order = self._make_order(self.other_user.id)
        self.db.commit()
        self.order_id = self.order.id
        self.owner_id = self.owner.id
        self.other_user_id = self.other_user.id
        self.db.close()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        main.app.dependency_overrides[main.get_db] = override_get_db
        main.engine.echo = False
        self.client = TestClient(main.app)
        self.owner_headers = self._auth_headers(self.owner_id, "customer")
        self.other_headers = self._auth_headers(self.other_user_id, "customer")
        self.admin_headers = self._auth_headers(self.owner_id, "admin")
        self.env_patcher = patch.dict(
            os.environ,
            {
                "STRIPE_SECRET_KEY": "sk_test_unit_fake",
                "STRIPE_WEBHOOK_SECRET": "whsec_unit_fake"
            }
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        main.app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def _make_order(self, user_id):
        order = models.Order(
            user_id=user_id,
            total_amount=Decimal("24.68"),
            status="PENDING",
            stock_restored=False
        )
        self.db.add(order)
        self.db.flush()
        self.db.add(models.OrderItem(
            order_id=order.id,
            product_id=self.product.id,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            subtotal=Decimal("24.68")
        ))
        self.db.flush()
        return order

    @staticmethod
    def _auth_headers(user_id, role):
        token = create_access_token({"sub": str(user_id), "role": role})
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _intent(
        intent_id="pi_test_123",
        intent_status="requires_payment_method",
        last_error=None
    ):
        return {
            "id": intent_id,
            "client_secret": "pi_test_client_secret",
            "status": intent_status,
            "last_payment_error": last_error
        }

    def _create_payment(self, order_id=None, headers=None):
        return self.client.post(
            "/payments/create",
            json={"order_id": order_id or self.order_id},
            headers=headers or self.owner_headers
        )

    def _get_payment(self, payment_id, headers=None):
        return self.client.get(
            f"/payments/{payment_id}",
            headers=headers or self.owner_headers
        )

    def _payment_row(self, payment_id):
        db = self.Session()
        try:
            return db.query(models.Payment).filter(
                models.Payment.id == payment_id
            ).one()
        finally:
            db.close()

    def _order_status(self, order_id=None):
        db = self.Session()
        try:
            order = db.query(models.Order).filter_by(
                id=order_id or self.order_id
            ).one()
            return order.status
        finally:
            db.close()

    def _payment_count(self):
        db = self.Session()
        try:
            return db.query(models.Payment).count()
        finally:
            db.close()

    @staticmethod
    def _signature(payload, secret="whsec_unit_fake"):
        timestamp = str(int(time.time()))
        signed_payload = timestamp.encode() + b"." + payload
        digest = hmac.new(
            secret.encode(),
            signed_payload,
            hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={digest}"

    def _webhook_payload(self, event_id, event_type, intent_id):
        return json.dumps({
            "id": event_id,
            "type": event_type,
            "data": {"object": {"id": intent_id}}
        }).encode()

    def _insert_payment(self, order_id, user_id, intent_id, status="PENDING"):
        db = self.Session()
        try:
            payment = models.Payment(
                order_id=order_id,
                user_id=user_id,
                amount=Decimal("24.68"),
                currency="inr",
                status=status,
                stripe_payment_intent_id=intent_id
            )
            db.add(payment)
            db.commit()
            db.refresh(payment)
            return payment.id
        finally:
            db.close()

    @patch("main.create_payment_intent")
    def test_create_uses_database_amount_and_returns_client_secret(self, create_intent):
        create_intent.return_value = self._intent()
        response = self._create_payment()

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["amount"], "24.68")
        self.assertEqual(body["currency"], "inr")
        self.assertEqual(body["status"], "PENDING")
        self.assertEqual(body["client_secret"], "pi_test_client_secret")
        self.assertEqual(create_intent.call_args.kwargs["amount"], 2468)
        self.assertEqual(create_intent.call_args.kwargs["currency"], "inr")
        self.assertEqual(self._order_status(), "PENDING")

    @patch("main.retrieve_payment_intent")
    @patch("main.create_payment_intent")
    def test_pending_intent_is_reused(self, create_intent, retrieve_intent):
        create_intent.return_value = self._intent()
        first = self._create_payment()
        retrieve_intent.return_value = self._intent()
        second = self._create_payment()

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            second.json()["payment_id"],
            first.json()["payment_id"]
        )
        create_intent.assert_called_once()
        self.assertEqual(self._payment_count(), 1)

    def test_unauthenticated_and_other_user_access_are_rejected(self):
        unauthenticated = self.client.post(
            "/payments/create",
            json={"order_id": self.order_id}
        )
        wrong_order = self._create_payment(
            order_id=self.order_id,
            headers=self.other_headers
        )
        payment_id = self._insert_payment(
            self.order_id,
            self.owner_id,
            "pi_owner_only"
        )
        wrong_payment = self._get_payment(payment_id, self.other_headers)

        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(wrong_order.status_code, 404)
        self.assertEqual(wrong_payment.status_code, 404)
        self.assertEqual(self._get_payment(999999).status_code, 404)

    def test_cancelled_and_successfully_paid_orders_cannot_be_paid(self):
        db = self.Session()
        cancelled = db.query(models.Order).filter_by(id=self.order_id).one()
        cancelled.status = "CANCELLED"
        db.commit()
        db.close()
        self.assertEqual(self._create_payment().status_code, 400)

        db = self.Session()
        order = db.query(models.Order).filter_by(id=self.order_id).one()
        order.status = "PENDING"
        db.add(models.Payment(
            order_id=self.order_id,
            user_id=self.owner_id,
            amount=Decimal("24.68"),
            currency="inr",
            status="SUCCEEDED",
            stripe_payment_intent_id="pi_already_paid"
        ))
        db.commit()
        db.close()
        self.assertEqual(self._create_payment().status_code, 409)

    def test_missing_or_live_secret_is_rejected_without_payment_row(self):
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": ""}):
            missing = self._create_payment()
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_live_not_allowed"}):
            live = self._create_payment()

        self.assertEqual(missing.status_code, 503)
        self.assertEqual(live.status_code, 503)
        self.assertEqual(self._payment_count(), 0)

    @patch("main.create_payment_intent")
    @patch("main.retrieve_payment_intent")
    def test_payment_retrieval_confirms_order_only_on_success(
        self,
        retrieve_intent,
        create_intent
    ):
        create_intent.return_value = self._intent()
        created = self._create_payment().json()
        retrieve_intent.return_value = self._intent(
            intent_status="succeeded"
        )
        succeeded = self._get_payment(created["payment_id"])

        self.assertEqual(succeeded.status_code, 200)
        self.assertEqual(succeeded.json()["status"], "SUCCEEDED")
        self.assertNotIn("client_secret", succeeded.json())
        self.assertEqual(self._order_status(), "CONFIRMED")

    @patch("main.retrieve_payment_intent")
    @patch("main.create_payment_intent")
    def test_failed_payment_stays_unconfirmed(self, create_intent, retrieve_intent):
        create_intent.return_value = self._intent()
        created = self._create_payment().json()
        retrieve_intent.return_value = self._intent(
            intent_status="requires_payment_method",
            last_error={"code": "card_declined"}
        )
        response = self._get_payment(created["payment_id"])

        self.assertEqual(response.json()["status"], "FAILED")
        self.assertEqual(self._order_status(), "PENDING")

    @patch("main.create_payment_intent")
    def test_stripe_errors_are_generic_and_payment_is_failed(self, create_intent):
        create_intent.side_effect = main.PaymentProviderError
        response = self._create_payment()

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("sk_test", response.text)
        self.assertEqual(self._payment_count(), 1)
        payment = self._payment_row(1)
        self.assertEqual(payment.status, "FAILED")
        self.assertEqual(self._order_status(), "PENDING")

    def test_webhook_requires_configuration_and_valid_signature(self):
        payload = self._webhook_payload(
            "evt_invalid_signature",
            "payment_intent.succeeded",
            "pi_missing"
        )
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": ""}):
            missing_secret = self.client.post(
                "/payments/webhook",
                content=payload,
                headers={"Stripe-Signature": "invalid"}
            )
        invalid_signature = self.client.post(
            "/payments/webhook",
            content=payload,
            headers={"Stripe-Signature": "t=1,v1=invalid"}
        )

        self.assertEqual(missing_secret.status_code, 503)
        self.assertEqual(invalid_signature.status_code, 400)

    def test_webhook_is_idempotent_and_does_not_downgrade_success(self):
        payment_id = self._insert_payment(
            self.order_id,
            self.owner_id,
            "pi_webhook_success"
        )
        payload = self._webhook_payload(
            "evt_success",
            "payment_intent.succeeded",
            "pi_webhook_success"
        )
        headers = {"Stripe-Signature": self._signature(payload)}
        first = self.client.post(
            "/payments/webhook",
            content=payload,
            headers=headers
        )
        repeated = self.client.post(
            "/payments/webhook",
            content=payload,
            headers=headers
        )
        failure_payload = self._webhook_payload(
            "evt_late_failure",
            "payment_intent.payment_failed",
            "pi_webhook_success"
        )
        late_failure = self.client.post(
            "/payments/webhook",
            content=failure_payload,
            headers={"Stripe-Signature": self._signature(failure_payload)}
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(late_failure.status_code, 200)
        self.assertEqual(self._payment_row(payment_id).status, "SUCCEEDED")
        self.assertEqual(self._order_status(), "CONFIRMED")
        self.assertEqual(self._payment_count(), 1)

    def test_failed_webhook_does_not_confirm_order(self):
        payment_id = self._insert_payment(
            self.order_id,
            self.owner_id,
            "pi_webhook_failure"
        )
        payload = self._webhook_payload(
            "evt_failure",
            "payment_intent.payment_failed",
            "pi_webhook_failure"
        )
        response = self.client.post(
            "/payments/webhook",
            content=payload,
            headers={"Stripe-Signature": self._signature(payload)}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._payment_row(payment_id).status, "FAILED")
        self.assertEqual(self._order_status(), "PENDING")

    def test_payment_schema_contains_no_card_or_secret_fields(self):
        columns = set(models.Payment.__table__.columns.keys())
        forbidden_columns = {
            "cvv",
            "cvc",
            "card_number",
            "full_card_number",
            "stripe_secret_key"
        }
        frontend = (
            Path(__file__).resolve().parents[3]
            / "frontend"
            / "src"
            / "PaymentCheckout.jsx"
        ).read_text(encoding="utf-8")

        self.assertTrue(columns.isdisjoint(forbidden_columns))
        self.assertNotIn("STRIPE_SECRET_KEY", frontend)
        self.assertNotIn("cardNumber", frontend)
        self.assertNotIn("cvv", frontend.lower())


if __name__ == "__main__":
    unittest.main()