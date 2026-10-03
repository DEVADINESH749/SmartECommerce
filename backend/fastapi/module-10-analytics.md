# Module 10: Analytics Dashboard

## Purpose

The Django Admin analytics dashboard provides staff with read-only order, revenue, payment, product, and inventory summaries using the existing unmanaged Product, Order, OrderItem, Payment, and User models. It creates no tables and inserts no analytics records.

## Dashboard URL

Open `/admin/analytics/` on the Django service (normally `http://127.0.0.1:8001/admin/analytics/`). The view is wrapped with Django Admin's `admin_view`; active Django staff and superusers can access it, while customers and other non-staff users are redirected to sign-in or denied.

There is no separate FastAPI analytics endpoint. Analytics are rendered server-side by Django and do not expose a public API.

## Calculations

- **Total orders** counts orders created in the selected date range.
- **Successful orders** and **order revenue** include `CONFIRMED`, `PROCESSING`, `SHIPPED`, and `DELIVERED` orders. `PENDING` and `CANCELLED` orders are excluded from revenue.
- **Daily sales** and **monthly sales** aggregate successful orders by creation date and sum `orders.total_amount`; empty buckets display zero.
- **Top-selling products** aggregate historical `order_items.quantity` and `subtotal` by product ID/name, restricted to successful orders in the selected range. Cancelled and pending order items are excluded. Results are ordered by quantity sold and limited to ten rows.
- **Low stock** counts active products with stock less than or equal to five and shows their ID, name, current stock, and price. This is a current inventory metric, not date-filtered.
- **Total products** and **total customers** are current counts. Customers are users with role `customer`.
- **Order status** groups all six order statuses within the selected date range, including zero-count statuses.
- **Payment status** groups all four payment statuses by payment creation date. Successful payment revenue sums `SUCCEEDED` payment amounts for the selected range.

Monetary values are presented in INR, matching the current single-currency project configuration.

## Date Filters

The default is the current month. Quick ranges include today, the last 7 days, the last 30 days, this month, and this year. A custom inclusive date range is also supported and limited to 366 days. Sales, order totals/statuses, top products, and payment counts/revenue use the selected range. Product/customer totals and low-stock inventory remain current-state metrics.

## Performance and Security

Counts, sums, date truncation, and product ranking use Django ORM database aggregates. The dashboard reads existing rows only. It does not include payment IDs, Stripe credentials, passwords, JWTs, or other authentication secrets in its output.

## Tests Performed

- Dashboard returns successfully for a Django superuser and an ordinary staff user; a non-staff user is denied.
- Summary totals, order/payment status counts, successful payment revenue, and date filtering.
- Cancelled order revenue and product quantities are excluded.
- Top product ordering and historical item revenue.
- Active-only low-stock threshold behavior.
- Existing API-owned models are reused without migrations.
- Full FastAPI regression suite, Django system check, Django Admin/analytics tests, and frontend production build.

## Test Results

Verified in this implementation run:

- `python manage.py check`: passed with no issues.
- `python manage.py test catalog_admin`: 8 tests passed.
- FastAPI `pytest -q`: 35 tests passed.
- Frontend `npm run build`: passed.

The FastAPI suite reports a non-failing Starlette/httpx deprecation warning. Vite reports a non-failing warning about the current CommonJS-loaded ESM config. Re-run these commands after local changes.

## Known Limitations

- Charts use lightweight CSS bars; no chart dependency is installed.
- Custom ranges are capped at 366 days to bound query and rendering size.
- Revenue display assumes the application's current INR currency convention; mixed-currency payment data would need per-currency totals before being combined.
- Low-stock threshold is currently a fixed value of five.
