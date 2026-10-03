# Module 9: Django Admin Panel

## Overview

Django Admin provides staff access to the existing Smart E-Commerce users, products, orders, order items, payments, and notifications. FastAPI-owned tables are mapped as unmanaged Django models (`managed = False`); this module does not create or migrate those tables.

## Admin URL

Run Django from `backend/django` with `python manage.py runserver 8001`, then open `http://127.0.0.1:8001/admin/`.

## Management

- **Users:** Search by name or email; filter by role, active state, and creation date. Staff can edit profile fields, role, and active state. Password hashes are excluded from forms and lists.
- **Products:** Add, edit, and delete products, including price, stock, category, popularity, and active state. The existing `products` table has no `updated_at` column, so the list identifies that value as untracked.
- **Orders:** Inspect the customer, total, timestamps, status, and read-only historical order items. Only status can be changed; add/delete and historical item editing are disabled.
- **Order items:** Available as read-only records and as an inline on each order.
- **Payments:** Read-only payment records, including the Stripe PaymentIntent ID. Admin does not create or alter payments or Stripe state.
- **Notifications:** Read-only notification history; existing rows cannot be added, changed, or deleted through Admin.

Order status changes call the same FastAPI order-status service used by `/admin/orders/{order_id}/status`. This retains cancellation stock restoration, transition validation, notification generation, and existing email behavior. No notification or email is sent for an unchanged status; notification event keys prevent duplicate status notifications.

## Permissions

Django's existing authentication and `is_staff`, `is_superuser`, model permissions, and groups protect Admin. Customers without Django staff access cannot enter Admin. Grant only the model permissions each staff member needs.

## Security

The User Admin never renders password hashes. Payment and notification records are read-only, and payment configuration secrets, JWTs, SMTP credentials, and provider secrets are not exposed by these Admin models. The shared status service reads the existing FastAPI environment configuration for its existing email sender; credentials are not stored in Django models.

## Testing

Install Django dependencies with `python -m pip install -r requirements.txt` from `backend/django`. Run `python manage.py check` and `python manage.py test catalog_admin` there. The Django test runner uses its isolated test database; unmanaged tables are created only inside that test database and removed afterward.

The existing FastAPI suite remains `pytest -q` from `backend/fastapi`. The frontend build remains `npm run build` from `frontend`.

## Manual Verification

Sign in at `/admin/` with an existing Django staff or superuser account. Verify the Users, Products, Orders, Order Items, Payments, and Notifications sections; exercise the supported search and filters; and confirm order status transitions through the shared service. Do not use existing production orders as test fixtures.

## Database Preservation

No migrations or schema creation are required for the six API-owned tables. Django Admin reads and updates their existing rows in place. The module does not reset the database or delete existing data. Product `updated_at` is not present in the inspected schema and is displayed as untracked.