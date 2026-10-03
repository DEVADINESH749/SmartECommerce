import { useState } from "react";
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe
} from "@stripe/react-stripe-js";
import { loadStripe } from "@stripe/stripe-js";
import { Component } from "react";
import { apiRequest } from "./api";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");
const configuredPublishableKey = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY;
const publishableKey = configuredPublishableKey?.startsWith("pk_test_")
  ? configuredPublishableKey
  : "";
const stripePromise = publishableKey ? loadStripe(publishableKey) : null;

async function responseData(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed (${response.status})`);
  }
  return data;
}

export function StripePaymentForm({ payment, accessToken, onClose, onPaid, returnUrl }) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const confirmPayment = async (event) => {
    event.preventDefault();
    if (!stripe || !elements) return;

    setBusy(true);
    setError("");

    try {
      const result = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: returnUrl || window.location.href
        },
        redirect: "if_required"
      });

      if (result.error) {
        setError(result.error.message || "Payment could not be completed.");
        return;
      }

      const paymentStatus = await apiRequest(`/payments/${payment.payment_id}`, {
        token: accessToken
      });

      if (paymentStatus.status === "SUCCEEDED") {
        await onPaid(paymentStatus.order_id);
      } else if (paymentStatus.status === "FAILED") {
        setError("Payment failed. You can start another attempt from the order.");
      } else {
        setError(`Payment status: ${paymentStatus.status}`);
      }
    } catch (requestError) {
      setError(requestError.message || "Payment could not be verified.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={confirmPayment}>
      <h4>Pay order #{payment.order_id}</h4>
      <PaymentElement
        onLoadError={() => setError("Secure payment details could not be loaded. Please try again.")}
      />
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={!stripe || busy}>
        {busy ? "Processing..." : "Pay securely"}
      </button>{" "}
      <button type="button" onClick={onClose} disabled={busy}>
        Cancel
      </button>
    </form>
  );
}

class StripeElementBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="notice notice-error" role="alert">
          Secure payment details could not be loaded. Close checkout and try again.
          <button className="button button-outline button-small" type="button" onClick={this.props.onClose}>Close</button>
        </div>
      );
    }
    return this.props.children;
  }
}

export function StripePayment({ payment, accessToken, onClose, onPaid, returnUrl }) {
  if (!stripePromise) return null;
  return (
    <StripeElementBoundary key={payment.payment_id} onClose={onClose}>
      <Elements stripe={stripePromise} options={{ clientSecret: payment.client_secret }}>
        <StripePaymentForm
          payment={payment}
          accessToken={accessToken}
          onClose={onClose}
          onPaid={onPaid}
          returnUrl={returnUrl}
        />
      </Elements>
    </StripeElementBoundary>
  );
}

function timeAgo(value) {
  const seconds = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 1000)
  );
  const relativeTime = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (seconds < 60) return relativeTime.format(-seconds, "second");
  if (seconds < 3600) return relativeTime.format(-Math.floor(seconds / 60), "minute");
  if (seconds < 86400) return relativeTime.format(-Math.floor(seconds / 3600), "hour");
  return relativeTime.format(-Math.floor(seconds / 86400), "day");
}

function PaymentCheckout() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [orders, setOrders] = useState([]);
  const [payment, setPayment] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  const loadOrders = async (token) => {
    const response = await fetch(`${API_BASE_URL}/orders`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const data = await responseData(response);
    setOrders(data);
  };

  const loadNotifications = async (token) => {
    const [listResponse, countResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/notifications?limit=50`, {
        headers: { Authorization: `Bearer ${token}` }
      }),
      fetch(`${API_BASE_URL}/notifications/unread-count`, {
        headers: { Authorization: `Bearer ${token}` }
      })
    ]);
    const [list, count] = await Promise.all([
      responseData(listResponse),
      responseData(countResponse)
    ]);
    setNotifications(list);
    setUnreadCount(count.unread_count);
  };

  const toggleNotifications = async () => {
    const shouldOpen = !notificationsOpen;
    setNotificationsOpen(shouldOpen);
    if (!shouldOpen || !accessToken) return;

    try {
      await loadNotifications(accessToken);
    } catch (requestError) {
      setError(requestError.message || "Could not load notifications.");
    }
  };

  const markNotificationRead = async (notificationId) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/notifications/${notificationId}/read`,
        {
          method: "PUT",
          headers: { Authorization: `Bearer ${accessToken}` }
        }
      );
      const notification = await responseData(response);
      setNotifications((current) => current.map((item) => (
        item.id === notification.id ? notification : item
      )));
      setUnreadCount((count) => Math.max(0, count - 1));
    } catch (requestError) {
      setError(requestError.message || "Could not update notification.");
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/notifications/read-all`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${accessToken}` }
      });
      await responseData(response);
      setNotifications((current) => current.map((item) => ({
        ...item,
        is_read: true
      })));
      setUnreadCount(0);
    } catch (requestError) {
      setError(requestError.message || "Could not update notifications.");
    }
  };

  const login = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await responseData(response);
      setAccessToken(data.access_token);
      setPassword("");
      await Promise.all([
        loadOrders(data.access_token),
        loadNotifications(data.access_token)
      ]);
    } catch (requestError) {
      setError(requestError.message || "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  const startPayment = async (orderId) => {
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(`${API_BASE_URL}/payments/create`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ order_id: orderId })
      });
      const data = await responseData(response);
      setPayment(data);
    } catch (requestError) {
      setError(requestError.message || "Could not start payment.");
    } finally {
      setBusy(false);
    }
  };

  const paymentSucceeded = async (orderId) => {
    setPayment(null);
    setMessage(`Payment succeeded. Order #${orderId} is confirmed.`);
    await Promise.all([
      loadOrders(accessToken),
      loadNotifications(accessToken)
    ]);
  };

  return (
    <section aria-labelledby="payment-checkout-title">
      <h2 id="payment-checkout-title">Orders and payment</h2>

      {!accessToken ? (
        <form onSubmit={login}>
          <label>
            Account email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>{" "}
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>{" "}
          <button type="submit" disabled={busy}>
            {busy ? "Signing in..." : "View my orders"}
          </button>
        </form>
      ) : (
        <>
          <button
            type="button"
            onClick={() => {
              setAccessToken("");
              setOrders([]);
              setPayment(null);
              setMessage("");
            }}
          >
            Sign out of checkout
          </button>
          <button
            type="button"
            aria-label={`Notifications, ${unreadCount} unread`}
            aria-expanded={notificationsOpen}
            onClick={toggleNotifications}
          >
            <span aria-hidden="true">🔔</span> {unreadCount}
          </button>
          {notificationsOpen && (
            <section aria-label="Notifications">
              <h3>Notifications</h3>
              {unreadCount > 0 && (
                <button type="button" onClick={markAllNotificationsRead}>
                  Mark all as read
                </button>
              )}
              {notifications.length === 0 ? (
                <p>No notifications.</p>
              ) : (
                <ul>
                  {notifications.map((notification) => (
                    <li
                      key={notification.id}
                      style={{
                        borderLeft: notification.is_read
                          ? "3px solid transparent"
                          : "3px solid #176b87",
                        padding: "8px 12px",
                        backgroundColor: notification.is_read
                          ? "transparent"
                          : "#edf7fa"
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => markNotificationRead(notification.id)}
                        disabled={notification.is_read}
                        style={{
                          display: "block",
                          width: "100%",
                          border: 0,
                          background: "transparent",
                          textAlign: "left",
                          cursor: notification.is_read ? "default" : "pointer"
                        }}
                      >
                        <strong>{notification.title}</strong>
                        <br />
                        <span>{notification.message}</span>
                        <br />
                        <small>{timeAgo(notification.created_at)}</small>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
          {orders.length === 0 ? (
            <p>No orders to pay.</p>
          ) : (
            <ul>
              {orders.map((order) => (
                <li key={order.id}>
                  Order #{order.id} · {order.status} · {order.total_amount} INR
                  {order.status !== "CANCELLED" && (
                    <button
                      type="button"
                      onClick={() => startPayment(order.id)}
                      disabled={busy || Boolean(payment) || !stripePromise}
                    >
                      {busy ? "Starting..." : "Pay order"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {!stripePromise && (
        <p>Configure VITE_STRIPE_PUBLISHABLE_KEY with a Stripe test key to enable payment.</p>
      )}

      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}

      {payment && (
        !publishableKey ? (
          <p role="alert">Set VITE_STRIPE_PUBLISHABLE_KEY to enable checkout.</p>
        ) : (
          <Elements
            stripe={stripePromise}
            options={{ clientSecret: payment.client_secret }}
          >
            <StripePaymentForm
              payment={payment}
              accessToken={accessToken}
              onClose={() => setPayment(null)}
              onPaid={paymentSucceeded}
            />
          </Elements>
        )
      )}
    </section>
  );
}

export default PaymentCheckout;