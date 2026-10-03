# Module 4 - Shopping Cart

Cart endpoints use the existing FastAPI bearer JWT authentication. Send the
local access token returned by `POST /login` in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

Every cart operation is scoped to the authenticated user's database ID. Product
prices are read from the database; clients cannot set a cart price. Adding an
existing product increases its quantity, subject to its current stock. Cart
operations do not change product stock.

## Endpoints

### `GET /cart`

Returns the authenticated user's cart and total amount.

Example response:

```json
{
  "items": [
    {
      "id": 1,
      "product_id": 8,
      "product_name": "Wireless Mouse",
      "category": "Electronics",
      "price": 599.00,
      "quantity": 2,
      "subtotal": 1198.00
    }
  ],
  "total": 1198.00
}
```

### `POST /cart`

Adds a product, or increases the quantity of that product if already present.

Example request:

```json
{
  "product_id": 8,
  "quantity": 2
}
```

Returns the updated cart item with its current database price. Returns `404`
for an unknown product, `400` for an inactive product or a quantity exceeding
stock, and `422` for invalid request data.

### `PUT /cart/{cart_id}`

Sets the quantity for an item owned by the authenticated user.

Example request:

```json
{
  "quantity": 1
}
```

Returns the updated cart item. Returns `404` if the item is not owned by the
authenticated user, `400` if the quantity exceeds stock, and `422` if the
quantity is not positive.

### `DELETE /cart/{cart_id}`

Removes one cart item owned by the authenticated user. Returns `204` on
success and `404` when the item is not found for that user.

### `DELETE /cart`

Removes all cart items belonging to the authenticated user. Returns:

```json
{
  "message": "Cart cleared"
}
```