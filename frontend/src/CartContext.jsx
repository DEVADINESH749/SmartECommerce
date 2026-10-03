import { createContext, useContext, useEffect, useState } from "react";
import { apiRequest } from "./api";
import { useSession } from "./AuthContext";

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const { accessToken } = useSession();
  const [cartCount, setCartCount] = useState(0);

  const refreshCart = async () => {
    if (!accessToken) {
      setCartCount(0);
      return null;
    }
    const cart = await apiRequest("/cart", { token: accessToken });
    setCartCount(cart.items.reduce((total, item) => total + item.quantity, 0));
    return cart;
  };

  useEffect(() => {
    let active = true;
    if (!accessToken) {
      setCartCount(0);
      return () => { active = false; };
    }
    apiRequest("/cart", { token: accessToken })
      .then((cart) => {
        if (active) setCartCount(cart.items.reduce((total, item) => total + item.quantity, 0));
      })
      .catch(() => {
        if (active) setCartCount(0);
      });
    return () => { active = false; };
  }, [accessToken]);

  const addProduct = async (productId, quantity = 1) => {
    await apiRequest("/cart", {
      method: "POST",
      token: accessToken,
      body: { product_id: productId, quantity }
    });
    await refreshCart();
  };

  return (
    <CartContext.Provider value={{ cartCount, refreshCart, addProduct }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used within CartProvider");
  return context;
}
