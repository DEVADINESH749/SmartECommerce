import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useSession } from "./AuthContext";

function AuthShell({ eyebrow, title, children }) {
  return (
    <section className="auth-page page-container">
      <div className="auth-aside">
        <span className="eyebrow">SMART MARKET / ACCOUNT</span>
        <h1>Shopping should feel simple.</h1>
        <p>Save your basket, follow every delivery, and keep your essentials close.</p>
        <div className="auth-note"><span className="auth-note-mark" aria-hidden="true">S</span><span>One account for everything you order.</span></div>
      </div>
      <div className="auth-card">
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        {children}
      </div>
    </section>
  );
}

function PasswordField({ label, name, value, onChange, autoComplete, required = true }) {
  const [visible, setVisible] = useState(false);
  return (
    <label className="form-field" htmlFor={name}>
      <span>{label}</span>
      <span className="password-input-wrap">
        <input
          id={name}
          name={name}
          type={visible ? "text" : "password"}
          value={value}
          onChange={onChange}
          autoComplete={autoComplete}
          required={required}
          minLength={8}
        />
        <button className="password-toggle" type="button" onClick={() => setVisible((shown) => !shown)} aria-label={visible ? "Hide password" : "Show password"}>
          {visible ? "Hide" : "Show"}
        </button>
      </span>
    </label>
  );
}

export function LoginPage() {
  const { isAuthenticated, isLoading, auth0Error, signIn, signInWithProvider } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const destination = location.state?.from?.pathname || "/";

  useEffect(() => {
    if (isAuthenticated) navigate(destination, { replace: true });
  }, [isAuthenticated, navigate, destination]);

  if (isAuthenticated) return <Navigate to={destination} replace />;

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signIn(email.trim(), password);
      navigate(destination, { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
      setPassword("");
    }
  };

  return (
    <AuthShell eyebrow="WELCOME BACK" title="Sign in to your account">
      {(error || auth0Error) && <p className="notice notice-error" role="alert">{error || auth0Error}</p>}
      {isLoading && <p className="notice" role="status">Finishing secure sign-in…</p>}
      <form className="form-stack" onSubmit={submit}>
        <label className="form-field" htmlFor="login-email">
          <span>Email address</span>
          <input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <PasswordField label="Password" name="login-password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
        <button className="button button-primary button-wide" type="submit" disabled={busy || isLoading}>
          {busy ? <><span className="spinner" aria-hidden="true" /> Signing in…</> : "Sign in"}
        </button>
      </form>
      <div className="auth-divider"><span>or continue with</span></div>
      <div className="social-actions">
        <button className="button button-outline" type="button" onClick={() => signInWithProvider("google-oauth2")}>Google</button>
        <button className="button button-outline" type="button" onClick={() => signInWithProvider("facebook")}>Facebook</button>
      </div>
      <p className="auth-switch">New here? <Link to="/register">Create an account</Link></p>
    </AuthShell>
  );
}

export function RegisterPage() {
  const { isAuthenticated, register } = useSession();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (isAuthenticated) return <Navigate to="/" replace />;

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (password.length < 8) return setError("Use at least 8 characters for your password.");
    if (password !== confirmPassword) return setError("Those passwords do not match.");
    setBusy(true);
    try {
      await register({ name: name.trim(), email: email.trim(), password });
      navigate("/", { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
      setPassword("");
      setConfirmPassword("");
    }
  };

  return (
    <AuthShell eyebrow="JOIN SMART MARKET" title="Create your account">
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      <form className="form-stack" onSubmit={submit}>
        <label className="form-field" htmlFor="register-name"><span>Name</span><input id="register-name" type="text" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required /></label>
        <label className="form-field" htmlFor="register-email"><span>Email address</span><input id="register-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <PasswordField label="Password" name="register-password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" />
        <PasswordField label="Confirm password" name="confirm-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" />
        <button className="button button-primary button-wide" type="submit" disabled={busy}>
          {busy ? <><span className="spinner" aria-hidden="true" /> Creating account…</> : "Create account"}
        </button>
      </form>
      <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
    </AuthShell>
  );
}
