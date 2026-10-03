# Module 12: Responsive Customer Frontend

## Pages

The React/Vite application provides Home, Products, Product Details, Login, Register, Cart, Checkout, Payment Success, Payment Failure, Orders, Order Details, Notifications, Profile, and a not-found route. Shared layout elements include the responsive header, mobile menu, unread notification/cart counts, and compact multi-column footer.

## Responsive Design

The layout is mobile-first with breakpoints at 1050px, 800px, 600px, and 360px. Content uses a constrained responsive container, adaptive product grids, stacked mobile details and cart cards, a collapsible mobile navigation/filter panel, and responsive checkout/order/profile layouts. Reduced-motion preferences and visible keyboard focus are respected.

Responsive browser checks covered all 13 customer routes at 320, 360, 375, 390, 414, 430, 768, 820, 834, 1024, 1280, 1366, 1440, 1536, and 1920 pixels. The check found no horizontal overflow in 195 route/viewport combinations. Mobile menu and product-filter expansion were exercised at 320px. A mocked customer journey covered login, product detail, add-to-cart, checkout setup, payment-success state, orders, notifications, profile, and logout; write endpoints were intercepted and no production records were changed.

## Authentication

Local registration and email/password login continue using FastAPI's existing endpoints. Google and Facebook continue through the existing Auth0 provider connections. Auth0 ID tokens are verified by FastAPI against the configured issuer/JWKS/client audience and require a verified email before exchanging into a customer-only local JWT session. The session token is held in tab-scoped session storage and is never logged or rendered. Protected routes redirect guests to login; logout clears the local session and Auth0 session when present.

## Product and Cart Flow

Products and product details load from the public FastAPI catalog. Category, price range, and popularity/price sorting are client-side filters over current catalog results. Add-to-cart, quantity changes, and removal use the existing authenticated cart endpoints and enforce server stock rules. Empty/loading/error states are provided.

## Checkout and Stripe

Checkout creates an order through the existing FastAPI order flow and requests a payment intent through the existing payment endpoint. The existing Stripe PaymentElement is reused and lazy-loaded only for checkout. Card details remain within Stripe; the client secret is used only to initialize Stripe Elements and is not logged or persisted. Success routes verify order/payment state with the backend. The failure route offers retry and cart navigation.

A real Stripe charge was not submitted during visual testing. A valid authenticated customer session and Stripe test card are required for a live payment verification.

## Orders, Notifications, and Profile

Order history and details use existing customer order endpoints; pending/confirmed cancellation uses the existing order-cancel endpoint. Notification history and mark-read actions use existing notification endpoints. Profile shows only name, email, and sign-in provider; it does not display tokens, passwords, or secrets.

## Error, Loading, and Empty States

Central `apiRequest` handling maps network, 401, 403, 404, 422, and 5xx failures to customer-facing messages without showing stack traces. Product, cart, checkout, order, notification, and route transitions expose loading states. Empty catalog, cart, order, and notification states include useful next actions where applicable.

## Accessibility

The UI uses semantic sections, headings, forms, labels, button/link elements, alt text, accessible menu/filter expanded state, keyboard focus styles, a skip link, and reduced-motion support. Passwords are masked by default and can be toggled without being logged.

## Testing and Results

- Browser responsive checks: 195 page/viewport combinations; no horizontal overflow.
- Browser interaction checks: mobile menu and filter open; guest add-to-cart redirects to login; mocked local sign-in updated the cart badge without production writes.
- FastAPI regression suite and Auth0 exchange coverage: 38 tests passed with `python -m pytest` from `backend/fastapi`.
- Django Admin suite: 12 tests passed with `python manage.py test catalog_admin.tests` from `backend/django`.
- Django system check: passed with `python manage.py check` from `backend/django`.
- Frontend production build: passed with `npm run build` from `frontend`.
- No frontend test script is currently configured in `package.json`.

## Known Limitations

- Live Google/Facebook credential round trips require the configured Auth0 tenant and a verified account; browser testing did not perform an external sign-in.
- A real Stripe test payment was not submitted; checkout setup and the status journey were tested with mocked API responses. Stripe's HTTP test-mode and legacy PaymentElement warnings remain informational.
- The API's existing CORS configuration allows `http://localhost:5173`; use that origin for local Vite development.
- Product imagery uses remote Unsplash URLs with a local visual fallback; offline sessions may show the fallback.
- Vite emits a non-failing warning about the existing ESM config loaded through its current config loader.
