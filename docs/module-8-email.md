# Module 8 - Email Notifications

FastAPI sends transactional email for order placement, payment outcomes, and
order status changes. Delivery uses Python's standard-library email and SMTP
clients. Mail failures are logged with safe event labels and never roll back an
order, payment, in-app notification, or status update.

## SMTP Configuration

SMTP configuration belongs only in `backend/fastapi/.env`. The file is ignored
by Git. Copy the keys from `.env.example` if they are not already present, then
fill the values locally with settings from your email provider:

```dotenv
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=Smart E-Commerce
SMTP_USE_TLS=true
```

The application validates the host, port, sender, TLS setting, and paired
username/password fields when attempting delivery. STARTTLS is used when
`SMTP_USE_TLS=true`. Incomplete configuration results in a safe skip; no
password or provider response is logged. React has no SMTP settings.

## Email Service and Templates

`email_service.py` builds multipart `EmailMessage` objects with plain-text and
HTML alternatives, connects over SMTP, and raises only controlled configuration
or delivery exceptions. `email_templates.py` provides these templates:

- `order_created_email`
- `payment_success_email`
- `payment_failed_email`
- `order_processing_email`
- `order_shipped_email`
- `order_delivered_email`
- `order_cancelled_email`

Templates escape customer-provided HTML and include no credentials, tokens, card
numbers, CVV, or Stripe client secrets.

## Automatic Emails

- Successful order creation sends **Your Smart E-Commerce Order #<id> Has Been Placed** with the total. The order and `ORDER_CREATED` notification commit first.
- A first `payment_intent.succeeded` transition sends **Payment Successful — Order #<id>**. Payment/order state and `PAYMENT_SUCCESS` notification commit first.
- A first `payment_intent.payment_failed` transition sends **Payment Failed — Order #<id>**. The order remains unpaid and `PAYMENT_FAILED` remains in-app.
- Admin transitions to `PROCESSING`, `SHIPPED`, `DELIVERED`, or `CANCELLED` send their corresponding status email and preserve the in-app notification.
- A customer cancellation also sends the cancellation email.

Order-status emails are sent only when the status changes. Payment emails are
sent only on the first local transition to success or failure; duplicate Stripe
webhook delivery does not resend them. Email is attempted after the business
transaction commits and cannot change its outcome.

## Testing

From `backend/fastapi`, run:

```powershell
.\venv\Scripts\python.exe -m pytest
```

The suite mocks SMTP and Stripe and uses isolated SQLite databases; no real
email account or Stripe charge is required. It checks message formats, SMTP
success/failure, every event template, delivery-failure isolation, and duplicate
webhook/status behavior.

## Manual Verification

1. Configure SMTP values locally and restart FastAPI.
2. Place a new order with an existing local account and verify its order email.
3. Use Stripe test mode and the configured signed webhook to confirm success
   and failure emails.
4. Change a test order's status as admin and verify status messages; repeat the
   same status and verify no duplicate is sent.
5. Temporarily use an invalid SMTP host and verify the order/payment/status API
   still succeeds while the application logs only a safe delivery-failure
   message.
