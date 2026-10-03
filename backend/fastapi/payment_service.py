import os

import stripe
from dotenv import load_dotenv


load_dotenv()


class PaymentConfigurationError(Exception):
    pass


class PaymentProviderError(Exception):
    pass


class InvalidWebhookSignature(Exception):
    pass


def stripe_value(value, key: str, default=None):
    if isinstance(value, dict):
        return value.get(key, default)

    try:
        return value[key]
    except (KeyError, TypeError):
        return getattr(value, key, default)


def get_stripe_secret_key() -> str:
    secret_key = os.getenv("STRIPE_SECRET_KEY")

    if not secret_key or not secret_key.startswith("sk_test_"):
        raise PaymentConfigurationError

    return secret_key


def get_webhook_secret() -> str:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    if not webhook_secret or not webhook_secret.startswith("whsec_"):
        raise PaymentConfigurationError

    return webhook_secret


def create_payment_intent(
    *,
    amount: int,
    currency: str,
    metadata: dict[str, str],
    idempotency_key: str,
    secret_key: str
):
    try:
        return stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            metadata=metadata,
            idempotency_key=idempotency_key,
            api_key=secret_key
        )
    except stripe.StripeError as exc:
        raise PaymentProviderError from exc


def retrieve_payment_intent(payment_intent_id: str, secret_key: str):
    try:
        return stripe.PaymentIntent.retrieve(
            payment_intent_id,
            api_key=secret_key
        )
    except stripe.StripeError as exc:
        raise PaymentProviderError from exc


def construct_webhook_event(
    payload: bytes,
    signature: str,
    secret: str
):
    try:
        return stripe.Webhook.construct_event(
            payload,
            signature,
            secret
        )
    except (
        ValueError,
        stripe.SignatureVerificationError
    ) as exc:
        raise InvalidWebhookSignature from exc