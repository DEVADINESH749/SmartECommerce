# Module 6 - Payment / Stripe Checkout

This module creates Stripe PaymentIntents for existing orders and confirms
payment state through authenticated retrieval and signed webhooks. It is test
mode only. Stripe Elements collects card details directly with Stripe; the API
and database never receive or store a full card number or CVV.

## Configuration

Install the FastAPI dependencies with the project's virtual environment:

```powershell
cd backend/fastapi
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a local `backend/fastapi/.env` from `.env.example` and set:

- `STRIPE_SECRET_KEY`: a Stripe test secret beginning with `sk_test_`.
- `STRIPE_WEBHOOK_SECRET`: the test signing secret from Stripe CLI or the
  webhook endpoint configuration, beginning with `whsec_`.

Never commit `.env` or share its values. The root `.gitignore` excludes env
files. Set `frontend/.env` from its example with:

- `VITE_API_BASE_URL`, defaulting to `http://127.0.0.1:8000`.
- `VITE_STRIPE_PUBLISHABLE_KEY`: a Stripe test publishable key beginning with
  `pk_test_`. This key is intended for frontend use; never put the secret key
  in Vite variables.

Restart the FastAPI and Vite development servers after changing env files.

## Payment Model

The `payments` table stores order/user IDs, the server-calculated amount,
currency, status, Stripe PaymentIntent ID, and timestamps. Foreign keys refer
to the existing `orders` and `users` tables. No card number, CVV, or Stripe
secret is stored. A unique constraint on the PaymentIntent ID prevents
duplicate local mappings.

## Authentication

Payment endpoints use the existing FastAPI local bearer JWT and only allow the
owner of an order/payment. The React payment panel has a separate local account
sign-in because the existing order API uses local JWTs; it keeps that token in
component memory and does not alter the existing Auth0 Google/Facebook flow.
Admin access is not required to pay for an order.

```http
Authorization: Bearer <access_token>
```

## Endpoints

### `POST /payments/create`

Creates or reuses a pending Stripe PaymentIntent for an owned, non-cancelled
order. The request contains only the order ID; amount is read from MySQL and
sent to Stripe in paise for INR.

```json
{
  "order_id": 1
}
```

Example response:

```json
{
  "payment_id": 1,
  "order_id": 1,
  "amount": 1198.00,
  "currency": "inr",
  "status": "PENDING",
  "client_secret": "pi_test_client_secret"
}
```

The client secret is returned only to the authenticated order owner for Stripe
Elements. Stripe's secret API key is never returned. Repeating a request reuses
the pending PaymentIntent; an order with a successful Payment cannot be paid
again.

### `GET /payments/{payment_id}`

Retrieves the PaymentIntent from Stripe, synchronizes local status, and returns
the authenticated user's payment:

```json
{
  "id": 1,
  "order_id": 1,
  "amount": 1198.00,
  "currency": "inr",
  "status": "SUCCEEDED",
  "created_at": "2026-10-01T12:00:00",
  "updated_at": "2026-10-01T12:01:00"
}
```

### `POST /payments/webhook`

Stripe sends signed events to this endpoint. The API requires a valid
`Stripe-Signature` header and `STRIPE_WEBHOOK_SECRET`.
`payment_intent.succeeded` marks the payment `SUCCEEDED` and confirms the order;
`payment_intent.payment_failed` marks the payment `FAILED` without confirming
the order. Repeated events apply the same state idempotently.

For local delivery, run Stripe CLI:

```text
stripe listen --forward-to http://127.0.0.1:8000/payments/webhook
```

Set the signing secret printed by the CLI in the local environment only. Never
include it in source, logs, screenshots, or chat.

## Payment Flow and Order Status

The customer signs into the checkout panel with the existing local account,
selects an order, and enters card details in Stripe's hosted Payment Element.
Raw card data goes directly from Stripe.js to Stripe, not to FastAPI. Payment
creation does not confirm the order. A verified successful PaymentIntent
retrieved from Stripe or received by signed webhook changes the payment to
`SUCCEEDED` and the order to `CONFIRMED`. A failure leaves the order unpaid.

## Test Mode

Use only Stripe test keys and official Stripe test cards. For example, Stripe's
documented success card is `4242 4242 4242 4242`; the documented generic decline
card is `4000 0000 0000 0002`. Use any future expiry and any test CVC in the
Stripe Element. Card data is not submitted to or stored by this application.

Test missing configuration, ownership checks, duplicate attempts, successful
and failed PaymentIntents, webhook signature verification, and repeated webhook
delivery using mocked Stripe responses or Stripe CLI. No real payment should
be made.
