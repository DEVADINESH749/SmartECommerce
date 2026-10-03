import React from "react";
import ReactDOM from "react-dom/client";
import { Auth0Provider } from "@auth0/auth0-react";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./AuthContext";
import { CartProvider } from "./CartContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Auth0Provider
      domain="dev-ay3oucvrj1zve1ph.us.auth0.com"
      clientId="SGEhMn053XGgGwCD9Gt85XIL7VQR8o4R"
      authorizationParams={{
        redirect_uri: window.location.origin,
        audience: "https://smart-ecommerce-api",
        scope: "openid profile email"
      }}
    >
      <BrowserRouter>
        <AuthProvider>
          <CartProvider>
            <App />
          </CartProvider>
        </AuthProvider>
      </BrowserRouter>
    </Auth0Provider>
  </React.StrictMode>
);