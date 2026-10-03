import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiRequest, emitNotificationsChanged } from "./api";
import { useCart } from "./CartContext";
import { useSession } from "./AuthContext";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const publishableKey = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY;
const stripeConfigured = publishableKey?.startsWith("pk_test_") || false;
const StripePayment = lazy(() => import("./PaymentCheckout").then((module) => ({ default: module.StripePayment })));

function LoadingState({ label = "Loading" }) {
  return <div className="loading-state" role="status"><span className="spinner" aria-hidden="true" />{label}…</div>;
}
function EmptyState({ title, body, action, to = "/products" }) {
  return (
    <div className="empty-state">
      <span className="empty-mark" aria-hidden="true">—</span>
      <h2>{title}</h2>
      <p>{body}</p>
      {action && <Link className="button button-primary" to={to}>{action}</Link>}
    </div>
  );
}

function OrderStatus({ status }) {
  return <span className={`status-badge status-${status?.toLowerCase()}`}>{status?.toLowerCase()}</span>;
}

export function CartPage() {
  const { accessToken, isAuthenticated } = useSession();
  const { refreshCart } = useCart();
  const navigate = useNavigate();
  const [cart, setCart] = useState(null);
  const [stockByProduct, setStockByProduct] = useState({});
  const [loading, setLoading] = useState(true);
  const [busyItem, setBusyItem] = useState(null);
  const [error, setError] = useState("");

  const reload = async () => {
    const [nextCart, products] = await Promise.all([
      apiRequest("/cart", { token: accessToken }),
      apiRequest("/products")
    ]);
    setCart(nextCart);
    setStockByProduct(Object.fromEntries(products.map((product) => [product.id, product.stock])));
  };

  useEffect(() => {
    let active = true;
    if (!isAuthenticated) return () => { active = false; };
    Promise.all([apiRequest("/cart", { token: accessToken }), apiRequest("/products")])
      .then(([nextCart, products]) => {
        if (active) {
          setCart(nextCart);
          setStockByProduct(Object.fromEntries(products.map((product) => [product.id, product.stock])));
        }
      })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken, isAuthenticated]);

  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: { pathname: "/cart" } }} />;

  const changeQuantity = async (item, quantity) => {
    if (quantity < 1 || quantity > (stockByProduct[item.product_id] ?? item.quantity)) return;
    setBusyItem(item.id);
    setError("");
    try {
      await apiRequest(`/cart/${item.id}`, { method: "PUT", token: accessToken, body: { quantity } });
      await reload();
      await refreshCart();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyItem(null);
    }
  };

  const removeItem = async (item) => {
    setBusyItem(item.id);
    setError("");
    try {
      await apiRequest(`/cart/${item.id}`, { method: "DELETE", token: accessToken });
      await reload();
      await refreshCart();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyItem(null);
    }
  };

  if (loading) return <section className="page-container page-section"><LoadingState label="Loading your bag" /></section>;
  if (!cart?.items.length) return <section className="page-container page-section"><EmptyState title="Your bag is taking a breather." body="Find something useful for your everyday and it will be waiting here." action="Explore products" /></section>;

  return (
    <section className="page-container page-section">
      <div className="page-heading"><div><span className="eyebrow">YOUR SELECTION</span><h1>Your bag</h1><p>{cart.items.reduce((sum, item) => sum + item.quantity, 0)} items, ready when you are.</p></div></div>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      <div className="cart-layout">
        <div className="cart-items" aria-label="Cart items">{cart.items.map((item) => <article className="cart-item" key={item.id}>
          <div className="cart-item-image" aria-hidden="true">{item.product_name.slice(0, 1)}</div>
          <div className="cart-item-main"><span className="product-category">{item.category}</span><h2>{item.product_name}</h2><p>{money.format(Number(item.price))} each</p>
            <div className="quantity-control" aria-label={`Quantity for ${item.product_name}`}><button type="button" aria-label="Decrease quantity" disabled={busyItem === item.id || item.quantity <= 1} onClick={() => changeQuantity(item, item.quantity - 1)}>−</button><span aria-live="polite">{item.quantity}</span><button type="button" aria-label="Increase quantity" disabled={busyItem === item.id || item.quantity >= (stockByProduct[item.product_id] ?? item.quantity)} onClick={() => changeQuantity(item, item.quantity + 1)}>+</button></div>
          </div>
          <div className="cart-item-total"><strong>{money.format(Number(item.subtotal))}</strong><button className="text-button remove-button" type="button" onClick={() => removeItem(item)} disabled={busyItem === item.id}>Remove</button></div>
        </article>)}</div>
        <aside className="order-summary"><span className="eyebrow">ORDER SUMMARY</span><h2>Almost yours.</h2><div className="summary-line"><span>Items</span><strong>{cart.items.reduce((sum, item) => sum + item.quantity, 0)}</strong></div><div className="summary-line"><span>Subtotal</span><strong>{money.format(Number(cart.total))}</strong></div><div className="summary-line summary-total"><span>Total</span><strong>{money.format(Number(cart.total))}</strong></div><p className="summary-note">Shipping and any applicable taxes are shown at the next step.</p><button className="button button-primary button-wide" type="button" onClick={() => navigate("/checkout")}>Continue to checkout</button><Link className="text-link summary-continue" to="/products">Continue shopping</Link></aside>
      </div>
    </section>
  );
}

export function CheckoutPage() {
  const { accessToken, isAuthenticated } = useSession();
  const { refreshCart } = useCart();
  const [searchParams] = useSearchParams();
  const [cart, setCart] = useState(null);
  const [order, setOrder] = useState(null);
  const [payment, setPayment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const existingOrderId = searchParams.get("order");

  useEffect(() => {
    let active = true;
    if (!isAuthenticated) return () => { active = false; };
    const request = existingOrderId
      ? apiRequest(`/orders/${existingOrderId}`, { token: accessToken }).then(setOrder)
      : apiRequest("/cart", { token: accessToken }).then(setCart);
    request.catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken, existingOrderId, isAuthenticated]);

  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: { pathname: "/checkout" } }} />;

  const startPayment = async (targetOrder) => {
    setBusy(true);
    setError("");
    try {
      const result = await apiRequest("/payments/create", {
        method: "POST",
        token: accessToken,
        body: { order_id: targetOrder.id }
      });
      setOrder(targetOrder);
      setPayment(result);
    } catch (requestError) {
      if (requestError.status === 409) {
        navigate(`/payment/success?order=${targetOrder.id}`, { replace: true });
      } else {
        setError(requestError.message || "Payment could not be started.");
      }
    } finally {
      setBusy(false);
    }
  };

  const placeOrder = async () => {
    setBusy(true);
    setError("");
    try {
      const newOrder = await apiRequest("/orders", { method: "POST", token: accessToken });
      emitNotificationsChanged();
      setOrder(newOrder);
      setCart(null);
      await refreshCart();
      await startPayment(newOrder);
    } catch (requestError) {
      setError(requestError.message || "Your order could not be created.");
      setBusy(false);
    }
  };

  const paid = (orderId) => navigate(`/payment/success?order=${orderId}&payment=${payment.payment_id}`, { replace: true });

  if (loading) return <section className="page-container page-section"><LoadingState label="Preparing checkout" /></section>;
  if (error && !cart && !order) return <section className="page-container page-section"><div className="notice notice-error" role="alert">{error}</div><Link className="button button-outline" to="/cart">Back to bag</Link></section>;
  if (!order && !cart?.items.length) return <section className="page-container page-section"><EmptyState title="Nothing to check out yet." body="Add a few things to your bag first." action="Browse products" /></section>;

  return (
    <section className="page-container page-section">
      <div className="page-heading"><div><span className="eyebrow">SECURE CHECKOUT</span><h1>Checkout</h1><p>Your payment details are handled securely by Stripe.</p></div></div>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      <div className="checkout-layout">
        <section className="checkout-panel">
          <span className="step-label">01 / PAYMENT</span><h2>Payment details</h2>
          {!stripeConfigured && <p className="notice notice-error" role="alert">Secure checkout is not configured. Please contact support.</p>}
          {payment && stripeConfigured ? <Suspense fallback={<LoadingState label="Loading secure payment" />}><StripePayment payment={payment} accessToken={accessToken} onClose={() => setPayment(null)} onPaid={paid} returnUrl={`${window.location.origin}/payment/success?order=${order.id}&payment=${payment.payment_id}`} /></Suspense> : <div className="payment-placeholder"><span className="payment-lock" aria-hidden="true">Secure</span><p>Your card details are entered in Stripe’s secure payment form after you continue.</p><button className="button button-primary" type="button" onClick={() => order ? startPayment(order) : placeOrder()} disabled={busy || !stripeConfigured}>{busy ? <><span className="spinner" aria-hidden="true" /> Preparing…</> : order ? "Continue to payment" : "Place order and pay"}</button></div>}
          <p className="secure-note">Card numbers and security codes are sent directly to Stripe. They are never stored by Smart Market.</p>
        </section>
        <aside className="order-summary"><span className="eyebrow">YOUR ORDER</span><h2>Order summary</h2>{order ? <><div className="checkout-items">{order.items.map((item) => <div className="summary-line" key={item.id}><span>{item.product_name} × {item.quantity}</span><strong>{money.format(Number(item.subtotal))}</strong></div>)}</div><div className="summary-line summary-total"><span>Total</span><strong>{money.format(Number(order.total_amount))}</strong></div></> : <><div className="checkout-items">{cart.items.map((item) => <div className="summary-line" key={item.id}><span>{item.product_name} × {item.quantity}</span><strong>{money.format(Number(item.subtotal))}</strong></div>)}</div><div className="summary-line summary-total"><span>Total</span><strong>{money.format(Number(cart.total))}</strong></div></>}<Link className="text-link summary-continue" to="/cart">Back to bag</Link></aside>
      </div>
    </section>
  );
}

export function PaymentOutcomePage({ success }) {
  const { accessToken, isAuthenticated } = useSession();
  const [searchParams] = useSearchParams();
  const orderId = searchParams.get("order");
  const paymentId = searchParams.get("payment");
  const [order, setOrder] = useState(null);
  const [payment, setPayment] = useState(null);
  const [loading, setLoading] = useState(Boolean(success && orderId && accessToken));
  const [error, setError] = useState("");

  useEffect(() => {
    if (!success || !orderId || !accessToken) return undefined;
    let active = true;
    Promise.all([
      apiRequest(`/orders/${orderId}`, { token: accessToken }),
      paymentId ? apiRequest(`/payments/${paymentId}`, { token: accessToken }) : Promise.resolve(null)
    ]).then(([orderResult, paymentResult]) => {
      if (active) {
        setOrder(orderResult);
        setPayment(paymentResult);
        if (paymentResult?.status === "SUCCEEDED") emitNotificationsChanged();
      }
    }).catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken, orderId, paymentId, success]);

  if (success && !isAuthenticated) return <Navigate to="/login" replace state={{ from: { pathname: "/payment/success" } }} />;
  if (loading) return <section className="page-container page-section"><LoadingState label="Verifying payment" /></section>;
  const isPaid = success && order && (!paymentId || payment?.status === "SUCCEEDED");

  if (success && !isPaid) return <section className="page-container outcome-page"><div className="outcome-mark outcome-pending" aria-hidden="true">…</div><span className="eyebrow">PAYMENT STATUS</span><h1>We’re checking your payment.</h1><p>{error || "Your payment is still being confirmed. Check your orders in a moment."}</p><Link className="button button-primary" to="/orders">View orders</Link></section>;

  if (success) return <section className="page-container outcome-page"><div className="outcome-mark" aria-hidden="true">✓</div><span className="eyebrow">PAYMENT COMPLETE</span><h1>Payment successful.</h1><p>Your order is confirmed and we’ll keep you updated as it moves.</p><div className="outcome-receipt"><span>Order #{order.id}</span><strong>{money.format(Number(order.total_amount))}</strong><span><OrderStatus status={order.status} /></span></div><div className="outcome-actions"><Link className="button button-primary" to={`/orders/${order.id}`}>View order</Link><Link className="button button-outline" to="/products">Continue shopping</Link></div></section>;

  return <section className="page-container outcome-page"><div className="outcome-mark outcome-failed" aria-hidden="true">×</div><span className="eyebrow">PAYMENT NOT COMPLETE</span><h1>Payment could not be completed.</h1><p>{error || "Your order and bag are safe. You can try the payment again."}</p><div className="outcome-actions">{orderId ? <Link className="button button-primary" to={`/checkout?order=${orderId}`}>Try again</Link> : <Link className="button button-primary" to="/checkout">Try again</Link>}<Link className="button button-outline" to="/cart">Back to bag</Link></div></section>;
}

export function OrdersPage() {
  const { accessToken, isAuthenticated } = useSession();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    apiRequest("/orders", { token: accessToken })
      .then((data) => { if (active) setOrders(data); })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken]);

  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: { pathname: "/orders" } }} />;
  return <section className="page-container page-section"><div className="page-heading"><div><span className="eyebrow">YOUR PURCHASES</span><h1>Orders</h1><p>Every order, from checkout to your doorstep.</p></div></div>{error && <p className="notice notice-error" role="alert">{error}</p>}{loading ? <LoadingState label="Loading orders" /> : orders.length === 0 ? <EmptyState title="No orders yet." body="Your next everyday favorite is just around the corner." action="Explore products" /> : <div className="order-list">{orders.map((order) => <article className="order-card" key={order.id}><div className="order-card-top"><div><span className="product-category">ORDER</span><h2>#{order.id}</h2></div><OrderStatus status={order.status} /></div><div className="order-card-meta"><span>Placed <strong>{new Date(order.created_at).toLocaleDateString()}</strong></span><span>{order.item_count} {order.item_count === 1 ? "item" : "items"}</span><strong>{money.format(Number(order.total_amount))}</strong></div><Link className="text-link" to={`/orders/${order.id}`}>View details <span aria-hidden="true">→</span></Link></article>)}</div>}</section>;
}

export function OrderDetailPage() {
  const { orderId } = useParams();
  const { accessToken, isAuthenticated } = useSession();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadOrder = async () => setOrder(await apiRequest(`/orders/${orderId}`, { token: accessToken }));
  useEffect(() => {
    let active = true;
    apiRequest(`/orders/${orderId}`, { token: accessToken })
      .then((data) => { if (active) setOrder(data); })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken, orderId]);

  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: { pathname: `/orders/${orderId}` } }} />;
  const cancelOrder = async () => {
    setBusy(true);
    setError("");
    try { await apiRequest(`/orders/${orderId}/cancel`, { method: "POST", token: accessToken }); await loadOrder(); }
    catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };
  if (loading) return <section className="page-container page-section"><LoadingState label="Loading order" /></section>;
  if (error && !order) return <section className="page-container page-section"><p className="notice notice-error" role="alert">{error}</p><Link to="/orders">Back to orders</Link></section>;
  if (!order) return null;

  return <section className="page-container page-section"><Link className="back-link" to="/orders">← All orders</Link><div className="page-heading"><div><span className="eyebrow">ORDER DETAILS</span><h1>Order #{order.id}</h1><p>Placed {new Date(order.created_at).toLocaleString()}</p></div><OrderStatus status={order.status} /></div>{error && <p className="notice notice-error" role="alert">{error}</p>}<div className="order-detail-layout"><section className="checkout-panel"><h2>Items in this order</h2><div className="detail-order-items">{order.items.map((item) => <div className="detail-order-item" key={item.id}><div><strong>{item.product_name}</strong><span>{money.format(Number(item.unit_price))} × {item.quantity}</span></div><strong>{money.format(Number(item.subtotal))}</strong></div>)}</div><div className="summary-line summary-total"><span>Order total</span><strong>{money.format(Number(order.total_amount))}</strong></div></section><aside className="order-summary"><span className="eyebrow">ORDER STATUS</span><h2><OrderStatus status={order.status} /></h2><p>Last updated {new Date(order.updated_at).toLocaleString()}</p>{order.status === "PENDING" && <Link className="button button-primary button-wide" to={`/checkout?order=${order.id}`}>Pay this order</Link>}{["PENDING", "CONFIRMED"].includes(order.status) && <button className="button button-outline button-wide cancel-order" type="button" disabled={busy} onClick={cancelOrder}>{busy ? "Cancelling…" : "Cancel order"}</button>}</aside></div></section>;
}

export function NotificationsPage() {
  const { accessToken, isAuthenticated } = useSession();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const unreadCount = useMemo(() => notifications.filter((item) => !item.is_read).length, [notifications]);

  const load = async () => setNotifications(await apiRequest("/notifications?limit=100", { token: accessToken }));
  useEffect(() => {
    let active = true;
    apiRequest("/notifications?limit=100", { token: accessToken })
      .then((data) => { if (active) setNotifications(data); })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken]);

  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: { pathname: "/notifications" } }} />;
  const markRead = async (id) => {
    try {
      const updated = await apiRequest(`/notifications/${id}/read`, { method: "PUT", token: accessToken });
      setNotifications((current) => current.map((item) => item.id === id ? updated : item));
      emitNotificationsChanged();
    } catch (requestError) { setError(requestError.message); }
  };
  const markAllRead = async () => {
    try { await apiRequest("/notifications/read-all", { method: "PUT", token: accessToken }); emitNotificationsChanged(); await load(); }
    catch (requestError) { setError(requestError.message); }
  };

  return <section className="page-container page-section"><div className="page-heading"><div><span className="eyebrow">YOUR UPDATES</span><h1>Notifications</h1><p>{unreadCount ? `${unreadCount} unread update${unreadCount === 1 ? "" : "s"}` : "You’re all caught up."}</p></div>{unreadCount > 0 && <button className="button button-outline" type="button" onClick={markAllRead}>Mark all as read</button>}</div>{error && <p className="notice notice-error" role="alert">{error}</p>}{loading ? <LoadingState label="Loading notifications" /> : notifications.length === 0 ? <EmptyState title="No notifications yet." body="Order updates and account activity will appear here." /> : <div className="notification-list">{notifications.map((item) => <article className={`notification-card ${item.is_read ? "is-read" : "is-unread"}`} key={item.id}><span className="notification-mark" aria-hidden="true">{item.is_read ? "•" : "●"}</span><div className="notification-copy"><div className="notification-title-row"><h2>{item.title}</h2><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></div><p>{item.message}</p><span className="product-category">{item.notification_type.replaceAll("_", " ")}</span></div>{!item.is_read && <button className="text-button" type="button" onClick={() => markRead(item.id)}>Mark read</button>}</article>)}</div>}</section>;
}

export function ProfilePage() {
  const { user, isAuthenticated, signOut } = useSession();
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: { pathname: "/profile" } }} />;
  return <section className="page-container page-section"><div className="page-heading"><div><span className="eyebrow">YOUR ACCOUNT</span><h1>Profile</h1><p>Your account information, kept simple.</p></div></div><section className="profile-panel"><div className="profile-avatar" aria-hidden="true">{user?.name?.trim()?.[0]?.toUpperCase() || "S"}</div><dl className="profile-fields"><div><dt>Name</dt><dd>{user?.name || "Customer"}</dd></div><div><dt>Email</dt><dd>{user?.email}</dd></div><div><dt>Sign-in method</dt><dd>{user?.authProvider || "Local account"}</dd></div></dl><button className="button button-outline" type="button" onClick={signOut}>Sign out</button></section></section>;
}
