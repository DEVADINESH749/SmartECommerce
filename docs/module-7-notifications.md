# Module 7 - Notifications

Module 7 adds private, in-app notifications for order and payment events. It
uses the existing FastAPI bearer JWT and MySQL database. Notification creation
is part of the transaction that creates an order, changes an order status, or
processes a verified Stripe webhook.

## Database Model

The `notifications` table contains:

- `id`: notification ID.
- `user_id`: foreign key to the existing `users` table.
- `title` and `message`: required display text. Payment messages include only
  the order ID and result; they never include card or payment credentials.
- `notification_type`: constrained to a supported event type.
- `is_read`: defaults to false.
- `created_at`: database-generated creation time.
- `event_key`: optional unique idempotency key for order/webhook events.

An index on `(user_id, created_at)` supports user-scoped newest-first queries.
The existing user, order, product, cart, and payment records are not recreated.

## Authentication and Access

Send the existing local FastAPI JWT as a bearer token. Customers can only list,
count, or modify their own notifications. `GET /admin/notifications` is limited
to JWT roles `admin` and `staff` and can optionally filter by `user_id`.

```http
Authorization: Bearer <access_token>
```

## Customer API

### `GET /notifications`

Returns the current user's notifications, newest first. Optional query
parameters are `is_read=true|false`, `limit` (default 50, maximum 100), and
`offset` (default 0).

```text
GET /notifications?is_read=false&limit=20&offset=0
```

Example response:

```json
[
  {
    "id": 7,
    "user_id": 1,
    "title": "Payment successful",
    "message": "Payment for order #5 was successful.",
    "notification_type": "PAYMENT_SUCCESS",
    "is_read": false,
    "created_at": "2026-10-02T00:00:00"
  }
]
```

### `GET /notifications/unread-count`

Returns the user's unread count:

```json
{
  "unread_count": 3
}
```

### `PUT /notifications/{notification_id}/read`

Marks one owned notification as read and returns it. A missing ID or another
user's notification returns `404`.

### `PUT /notifications/read-all`

Marks all the authenticated user's unread notifications as read:

```json
{
  "updated_count": 3
}
```

## Admin API

### `GET /admin/notifications`

Admin/staff only. Returns newest-first notifications, with optional `user_id`,
`is_read`, `limit` (default 100, maximum 200), and `offset` filters. Customer
JWTs receive `403`.

## Notification Types and Triggers

- `ORDER_CREATED`: order transaction commits; title `Order placed`.
- `ORDER_CONFIRMED`: an admin changes an order to confirmed.
- `ORDER_PROCESSING`: an admin changes an order to processing.
- `ORDER_SHIPPED`: an admin changes an order to shipped.
- `ORDER_DELIVERED`: an admin changes an order to delivered.
- `ORDER_CANCELLED`: an order is cancelled by its owner or an admin.
- `PAYMENT_SUCCESS`: a verified `payment_intent.succeeded` Stripe webhook.
- `PAYMENT_FAILED`: a verified `payment_intent.payment_failed` Stripe webhook.

Webhook notification event keys are derived from Stripe event IDs so retrying a
webhook does not create duplicate notifications. Order creation also uses a
stable event key. Notifications are committed with their triggering database
changes. Repeating an unchanged admin status does not create a new notification.

## Frontend

The existing React checkout panel contains a bell button with an unread badge.
After local FastAPI sign-in, it loads the current user's notifications. Opening
the bell refreshes the list; clicking an unread entry marks it read, and a
separate action marks all as read. Unread entries are visually highlighted and
timestamps are shown relatively. Auth0 login and Stripe Elements are unchanged.

## WebSocket Status

No WebSocket endpoint is added. The current browser auth uses bearer headers;
WebSocket APIs do not support those custom headers in the browser, and moving a
JWT into a query string could expose it in access logs. The HTTP APIs and
frontend notification panel are implemented without changing authentication.
A future real-time channel should use a deliberate, browser-safe credential
handoff and connection authorization design.

## Run and Test

Start the FastAPI server from `backend/fastapi`:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

The table is created by the existing SQLAlchemy `Base.metadata.create_all()`
startup path. The frontend uses the existing Vite server at port 5173.

Run the backend unit suite from `backend/fastapi`:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

The notification and payment tests use isolated SQLite databases and mocked
Stripe API responses. The payment suite also verifies real Stripe webhook
signature construction with a test signing secret; no secret value is stored
in the repository.
