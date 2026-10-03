import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { apiRequest } from "./api";
import { useCart } from "./CartContext";
import { useSession } from "./AuthContext";

function NotificationLink({ compact = false }) {
  const { accessToken } = useSession();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let active = true;
    const refresh = () => {
      if (!accessToken) return;
      apiRequest("/notifications/unread-count", { token: accessToken })
        .then((result) => { if (active) setUnread(result.unread_count); })
        .catch(() => { if (active) setUnread(0); });
    };

    if (!accessToken) {
      setUnread(0);
      return () => { active = false; };
    }

    refresh();
    window.addEventListener("smart-market:notifications-changed", refresh);
    return () => {
      active = false;
      window.removeEventListener("smart-market:notifications-changed", refresh);
    };
  }, [accessToken]);

  return (
    <NavLink className={compact ? "mobile-notifications" : "nav-link"} to="/notifications" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}>
      {compact ? <><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>{unread > 0 && <span className="mobile-notice-dot">{unread > 9 ? "9+" : unread}</span>}</> : <>Notifications{unread > 0 && <span className="nav-count">{unread > 99 ? "99+" : unread}</span>}</>}
    </NavLink>
  );
}

export function SiteLayout() {
  const { isAuthenticated, user, signOut } = useSession();
  const { cartCount } = useCart();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setMenuOpen(false), [location.pathname]);

  const navLinks = (
    <>
      <NavLink className="nav-link" to="/" end>Home</NavLink>
      <NavLink className="nav-link" to="/products">Products</NavLink>
      {isAuthenticated && <NavLink className="nav-link" to="/orders">Orders</NavLink>}
      {isAuthenticated && <NotificationLink />}
      {isAuthenticated && <NavLink className="nav-link" to="/profile">Profile</NavLink>}
    </>
  );

  return (
    <div className="site-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header">
        <div className="header-inner page-container">
          <Link className="brand" to="/" aria-label="Smart E-Commerce home">
            <span className="brand-mark" aria-hidden="true">S</span>
            <span>smart<span className="brand-light">market</span></span>
          </Link>
          <nav className="desktop-nav" aria-label="Main navigation">{navLinks}</nav>
          <div className="header-actions">
            {isAuthenticated && <NotificationLink compact />}
            <Link className="header-cart" to="/cart" aria-label={`Cart, ${cartCount} items`}>
              <span aria-hidden="true">Bag</span><span className="cart-count">{cartCount}</span>
            </Link>
            {isAuthenticated ? (
              <button className="button button-small button-quiet desktop-signout" type="button" onClick={signOut}>Sign out</button>
            ) : (
              <Link className="button button-small button-primary desktop-signin" to="/login">Sign in</Link>
            )}
            <button
              className="menu-toggle"
              type="button"
              aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={menuOpen}
              aria-controls="mobile-navigation"
              onClick={() => setMenuOpen((open) => !open)}
            >
              <span aria-hidden="true">{menuOpen ? "Close" : "Menu"}</span>
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav id="mobile-navigation" className="mobile-nav page-container" aria-label="Mobile navigation">
            {navLinks}
            {isAuthenticated ? (
              <button className="nav-link mobile-signout" type="button" onClick={signOut}>Sign out{user?.name ? `, ${user.name}` : ""}</button>
            ) : (
              <Link className="nav-link" to="/login">Sign in</Link>
            )}
          </nav>
        )}
      </header>
      <main id="main-content" className="main-content"><Outlet /></main>
      <footer className="site-footer">
        <div className="page-container footer-grid">
          <div className="footer-brand">
            <Link className="brand brand-footer" to="/">
              <span className="brand-mark" aria-hidden="true">S</span><span>smart<span className="brand-light">market</span></span>
            </Link>
            <p>Thoughtful everyday essentials, delivered with care.</p>
          </div>
          <div><h2>Explore</h2><Link to="/products">Shop all</Link><Link to="/orders">Your orders</Link></div>
          <div><h2>Customer care</h2><a href="mailto:support@smartmarket.example">Contact support</a><Link to="/notifications">Notifications</Link></div>
          <div><h2>About</h2><p>Good finds for everyday living.</p></div>
        </div>
        <div className="page-container footer-bottom">© {new Date().getFullYear()} Smart Market</div>
      </footer>
    </div>
  );
}
