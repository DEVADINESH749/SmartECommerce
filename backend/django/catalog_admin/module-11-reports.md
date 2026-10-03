# Module 11: Reports

## Purpose and URL

The Reports page provides authenticated Django staff/admin users read-only sales, orders, inventory, top-product, and payment reports using the existing unmanaged business models. It adds no business tables and does not mutate report data.

Dashboard: `/admin/reports/` (normally `http://127.0.0.1:8001/admin/reports/`). Both the page and every export route are wrapped with Django Admin's staff authorization. Anonymous users are redirected to login; non-staff users are denied.

## Available Reports and Date Filtering

The page includes sales, orders/status, products/inventory, top products, and payments/status summaries. Date filters are Today, Last 7 days, Last 30 days, This month, This year, and Custom range. The default is This month; custom ranges are inclusive and limited to 366 days.

Date filtering applies to order, sales, top-product, and payment reports. Product inventory and product totals reflect current state and are not date-filtered. On-screen order, product, and payment tables are paginated; CSV exports include all applicable rows.

## Revenue Rules

Successful sales include orders in `CONFIRMED`, `PROCESSING`, `SHIPPED`, and `DELIVERED` states. `PENDING` and `CANCELLED` orders are excluded from sales revenue, quantity sold, average order value, and top products. Sales totals use `orders.total_amount`; product quantity and revenue use historical `order_items.quantity` and `order_items.subtotal`. Payment successful revenue separately sums `SUCCEEDED` payment amounts.

Low stock means current stock less than or equal to five. Only active products appear in the low-stock section. Full inventory exports include both active and inactive products.

## Exports

- CSV: `sales_report.csv`, `orders_report.csv`, `inventory_report.csv`, and `payments_report.csv`.
- PDF: `sales_report.pdf` and `orders_report.pdf`, generated with ReportLab. PDFs include the title, generated timestamp, selected date range, summary values, and report table.

CSV output uses UTF-8 with a BOM and protects cells from spreadsheet formula execution. Exports contain business report fields only, not authentication or provider secrets.

## Authorization and Data Safety

Reports are GET-only and protected through Django Admin's existing staff authorization. Aggregates use database-side counts, sums, averages, and date grouping. Report queries only read existing data; they do not create, update, delete, or reset records. No duplicate product, order, order-item, or payment tables are created.

## Tests and Results

Verified test coverage includes anonymous/non-staff/staff access, sales totals and average order value, pending/cancelled exclusion, confirmed/fulfilled inclusion, top-product aggregates, low-stock rules, order/payment status summaries, selected date ranges, CSV content type and headers, PDF content type/signature, and Module 10 analytics/Admin regression tests.

- `python manage.py check`: passed with no issues.
- `python manage.py test catalog_admin.tests` from `backend/django`: 12 tests passed.
- FastAPI `pytest -q`: 35 tests passed.
- Frontend `npm run build`: passed.

## Known Warnings and Limitations

- The PDF dependency is ReportLab; install Django dependencies with `python -m pip install -r requirements.txt` from `backend/django`.
- Monetary display assumes the current single-currency INR convention. Mixed currencies would need separate totals.
- The existing FastAPI suite reports a non-failing Starlette/httpx deprecation warning. Vite reports a non-failing warning for its current config loader/module format.
