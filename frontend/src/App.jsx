import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useSession } from "./AuthContext";
import { SiteLayout } from "./Layout";

const { LoginPage, RegisterPage } = {
  LoginPage: lazy(() => import("./AuthPages").then((module) => ({ default: module.LoginPage }))),
  RegisterPage: lazy(() => import("./AuthPages").then((module) => ({ default: module.RegisterPage })))
};
const CartPage = lazy(() => import("./CustomerPages").then((module) => ({ default: module.CartPage })));
const CheckoutPage = lazy(() => import("./CustomerPages").then((module) => ({ default: module.CheckoutPage })));
const NotificationsPage = lazy(() => import("./CustomerPages").then((module) => ({ default: module.NotificationsPage })));
const OrderDetailPage = lazy(() => import("./CustomerPages").then((module) => ({ default: module.OrderDetailPage })));
const OrdersPage = lazy(() => import("./CustomerPages").then((module) => ({ default: module.OrdersPage })));
const PaymentOutcomePage = lazy(() => import("./CustomerPages").then((module) => ({ default: module.PaymentOutcomePage })));
const ProfilePage = lazy(() => import("./CustomerPages").then((module) => ({ default: module.ProfilePage })));
const HomePage = lazy(() => import("./StorePages").then((module) => ({ default: module.HomePage })));
const ProductDetailPage = lazy(() => import("./StorePages").then((module) => ({ default: module.ProductDetailPage })));
const ProductsPage = lazy(() => import("./StorePages").then((module) => ({ default: module.ProductsPage })));

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useSession();
  const location = useLocation();
  if (isLoading) return <div className="route-loading" role="status"><span className="spinner" aria-hidden="true" /> Securing your session…</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

function NotFoundPage() {
  return <section className="page-container page-section not-found"><span className="eyebrow">NOT FOUND / 404</span><h1>That page took a wrong turn.</h1><p>The page may have moved, but the useful things are still here.</p><a className="button button-primary" href="/products">Explore products</a></section>;
}

export default function App() {
  return (
    <Suspense fallback={<div className="route-loading" role="status"><span className="spinner" aria-hidden="true" /> Loading page…</div>}>
      <Routes>
        <Route element={<SiteLayout />}>
          <Route index element={<HomePage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="products/:productId" element={<ProductDetailPage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="register" element={<RegisterPage />} />
          <Route path="cart" element={<ProtectedRoute><CartPage /></ProtectedRoute>} />
          <Route path="checkout" element={<ProtectedRoute><CheckoutPage /></ProtectedRoute>} />
          <Route path="payment/success" element={<ProtectedRoute><PaymentOutcomePage success /></ProtectedRoute>} />
          <Route path="payment/failure" element={<ProtectedRoute><PaymentOutcomePage success={false} /></ProtectedRoute>} />
          <Route path="orders" element={<ProtectedRoute><OrdersPage /></ProtectedRoute>} />
          <Route path="orders/:orderId" element={<ProtectedRoute><OrderDetailPage /></ProtectedRoute>} />
          <Route path="notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
          <Route path="profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}