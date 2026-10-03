# Module 5 - Orders

Module 5 converts the authenticated user's current cart into a durable order.
Order lines retain product-name and unit-price snapshots so later product edits
do not change the historical order. Payments, Stripe, email, and notifications
are outside this module.

## Database Models

- `Order` stores its user, total, status, timestamps, and an internal
  `stock_restored` flag that prevents duplicate restocking.
- `OrderItem` stores its order/product references, product-name and unit-price
  snapshots, quantity, and subtotal.
- Order totals are calculated as the sum of `unit_price * quantity`.

The tables are created through the existing SQLAlchemy metadata setup. No
existing user, product, cart, or Django Admin table is recreated.

## Authentication and Authorization

Send the existing FastAPI bearer JWT in the `Authorization` header. Customer
routes use the authenticated user's database ID and only return that user's
orders. Admin routes use the existing `require_admin` dependency.

```http
Authorization: Bearer <access_token>
```

## Customer Endpoints

### `POST /orders`

Creates a pending order from the authenticated user's current cart. The request
has no body; prices are read from MySQL. The API rechecks active status and
stock, creates order snapshots, decreases stock, and clears the cart in one
transaction.

Example response:

```json
{
  "id": 1,
  "status": "PENDING",
  "total_amount": 1198.00,
  "created_at": "2026-10-01T12:00:00",
  "updated_at": "2026-10-01T12:00:00",
  "items": [
    {
      "id": 1,
      "product_id": 8,
      "product_name": "Wireless Mouse",
      "unit_price": 599.00,
      "quantity": 2,
      "subtotal": 1198.00
    }
  ]
}
```

An empty cart returns `400`. Missing, inactive, or insufficient-stock products
reject the transaction without creating a partial order or clearing the cart.

### `GET /orders`

Returns only the authenticated user's order history. `item_count` is the sum of
the ordered quantities across the order's lines.

Example response:

```json
[
  {
    "id": 1,
    "status": "PENDING",
    "total_amount": 1198.00,
    "created_at": "2026-10-01T12:00:00",
    "item_count": 2
  }
]
```

### `GET /orders/{order_id}`

Returns the full order and item snapshots. An order owned by another user is
reported as `404`.

### `POST /orders/{order_id}/cancel`

Customers may cancel only their own `PENDING` or `CONFIRMED` order. The
response is the updated order with status `CANCELLED`. Stock is restored once;
shipped, delivered, or already-cancelled orders cannot be cancelled by the
customer.

## Admin Endpoints

All admin endpoints require an existing admin JWT.

- `GET /admin/orders` returns all order summaries.
- `GET /admin/orders/{order_id}` returns the complete order.
- `PUT /admin/orders/{order_id}/status` updates the status and returns the
  complete order.

Example status request:

```json
{
  "status": "PROCESSING"
}
```

Allowed statuses are `PENDING`, `CONFIRMED`, `PROCESSING`, `SHIPPED`,
`DELIVERED`, and `CANCELLED`. An invalid status returns `422`. Setting status
to `CANCELLED` restores stock if it has not already been restored. A cancelled
order cannot be reopened, which preserves the inventory state.

## Order Lifecycle and Stock

New orders start as `PENDING`. Admins can update status through the allowed
values. Creating an order locks and rechecks its products, then decrements
stock, writes order snapshots, and clears the cart in one database transaction.
Adding items to a cart does not decrement stock. A permitted cancellation
restores each ordered quantity exactly once.