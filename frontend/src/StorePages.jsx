import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiRequest } from "./api";
import { useCart } from "./CartContext";
import { useSession } from "./AuthContext";

const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const mouseImage = "https://images.unsplash.com/photo-1527814050087-3793815479db?auto=format&fit=crop&w=1100&q=85";
const categoryImages = {
  Accessories: mouseImage,
  Electronics: mouseImage,
  default: "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=800&q=82"
};

function productImage(product) {
  return product.image || (product.name.toLowerCase().includes("mouse") ? mouseImage : categoryImages[product.category] || categoryImages.default);
}

function ProductCard({ product, onAdd }) {
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const add = async () => {
    setAdding(true);
    setError("");
    try {
      await onAdd(product.id);
    } catch (requestError) {
      if (requestError.status === 401) {
        navigate("/login", { state: { from: { pathname: "/products" } } });
      } else {
        setError(requestError.message);
      }
    } finally {
      setAdding(false);
    }
  };

  return (
    <article className="product-card">
      <Link className="product-image-link" to={`/products/${product.id}`} aria-label={`View ${product.name}`}>
        <img className="product-image" src={productImage(product)} alt={product.name} loading="lazy" onError={(event) => { event.currentTarget.src = categoryImages.default; }} />
        {product.stock <= 5 && <span className="stock-badge">Few left</span>}
      </Link>
      <div className="product-card-body">
        <span className="product-category">{product.category}</span>
        <h3><Link to={`/products/${product.id}`}>{product.name}</Link></h3>
        <div className="product-card-meta"><strong>{money.format(Number(product.price))}</strong><span>{product.stock > 0 ? `${product.stock} available` : "Out of stock"}</span></div>
        <div className="product-card-actions">
          <Link className="button button-outline button-small" to={`/products/${product.id}`}>Details</Link>
          <button className="button button-primary button-small" type="button" onClick={add} disabled={adding || product.stock < 1}>
            {adding ? "Adding…" : product.stock < 1 ? "Out of stock" : "Add to bag"}
          </button>
        </div>
        {error && <p className="field-error" role="alert">{error}</p>}
      </div>
    </article>
  );
}

function ProductGrid({ products, onAdd }) {
  if (!products.length) return <div className="empty-state"><span className="empty-mark" aria-hidden="true">—</span><h3>No products found</h3><p>Try a different category or clear your price filters.</p></div>;
  return <div className="product-grid">{products.map((product) => <ProductCard key={product.id} product={product} onAdd={onAdd} />)}</div>;
}

function ProductLoading() {
  return <div className="product-grid" aria-label="Loading products">{[1, 2, 3, 4].map((item) => <div className="skeleton product-skeleton" key={item}><span /><span /><span /></div>)}</div>;
}

export function HomePage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { addProduct } = useCart();
  const categories = useMemo(() => [...new Set(products.map((product) => product.category))].slice(0, 4), [products]);

  useEffect(() => {
    const controller = new AbortController();
    apiRequest("/products", { signal: controller.signal })
      .then(setProducts)
      .catch((requestError) => { if (requestError.name !== "AbortError") setError(requestError.message); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  return (
    <>
      <section className="home-hero">
        <div className="page-container hero-layout">
          <div className="hero-copy">
            <span className="eyebrow">USEFUL THINGS, WELL CHOSEN</span>
            <h1>Good finds for <em>everyday</em> living.</h1>
            <p>Smart essentials for work, home, and all the little routines in between.</p>
            <div className="hero-actions"><Link className="button button-primary" to="/products">Shop the collection</Link><Link className="text-link" to="/products">Browse all products <span aria-hidden="true">→</span></Link></div>
            <div className="hero-proof"><span className="proof-dot" /> Thoughtful picks · Clear prices · Easy checkout</div>
          </div>
          <div className="hero-visual">
            <img src={mouseImage} alt="Wireless computer mouse on a clean desk" fetchPriority="high" />
            <div className="hero-product-note"><span>WORKSPACE FAVORITE</span><strong>Wireless Mouse</strong><span>₹599 · ready to ship</span></div>
            <span className="hero-index">01 / EVERYDAY TECH</span>
          </div>
        </div>
      </section>

      <section className="page-container home-section" aria-labelledby="featured-heading">
        <div className="section-heading"><div><span className="eyebrow">THE WELL-USED EDIT</span><h2 id="featured-heading">Useful by design.</h2></div><Link className="text-link" to="/products">See everything <span aria-hidden="true">→</span></Link></div>
        {error && <p className="notice notice-error" role="alert">{error}</p>}
        {loading ? <ProductLoading /> : <ProductGrid products={products.slice(0, 4)} onAdd={addProduct} />}
      </section>

      {categories.length > 0 && <section className="category-band"><div className="page-container"><div className="section-heading"><div><span className="eyebrow">SHOP BY MOOD</span><h2>Start somewhere.</h2></div></div><div className="category-grid">{categories.map((category, index) => <Link className={`category-tile category-tile-${index + 1}`} key={category} to={`/products?category=${encodeURIComponent(category)}`}><span>{String(index + 1).padStart(2, "0")}</span><strong>{category}</strong><span className="category-arrow" aria-hidden="true">↗</span></Link>)}</div></div></section>}

      <section className="page-container home-section popular-section"><div className="section-heading"><div><span className="eyebrow">CUSTOMER FAVORITES</span><h2>Popular right now.</h2></div></div>{loading ? <ProductLoading /> : <ProductGrid products={[...products].sort((a, b) => b.popularity - a.popularity).slice(0, 4)} onAdd={addProduct} />}</section>

      <section className="promise-band"><div className="page-container promise-grid"><div><span className="eyebrow">A BETTER KIND OF BASKET</span><h2>Less noise.<br />More useful.</h2></div><p>We keep the essentials easy to find, prices easy to understand, and your orders easy to follow.</p><Link className="button button-light" to="/products">Find your next favorite</Link></div></section>
    </>
  );
}

export function ProductsPage() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const { addProduct } = useCart();
  const category = searchParams.get("category") || "all";
  const [minimum, setMinimum] = useState(searchParams.get("min_price") || "");
  const [maximum, setMaximum] = useState(searchParams.get("max_price") || "");
  const [sort, setSort] = useState("popular");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    apiRequest("/products", { signal: controller.signal })
      .then(setProducts)
      .catch((requestError) => { if (requestError.name !== "AbortError") setError(requestError.message); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const categories = useMemo(() => [...new Set(products.map((product) => product.category))].sort(), [products]);
  const visibleProducts = useMemo(() => {
    const result = products.filter((product) => (
      (category === "all" || product.category === category)
      && (!minimum || Number(product.price) >= Number(minimum))
      && (!maximum || Number(product.price) <= Number(maximum))
    ));
    if (sort === "price-low") result.sort((a, b) => Number(a.price) - Number(b.price));
    else if (sort === "price-high") result.sort((a, b) => Number(b.price) - Number(a.price));
    else result.sort((a, b) => b.popularity - a.popularity);
    return result;
  }, [products, category, minimum, maximum, sort]);

  const setCategory = (value) => {
    const next = new URLSearchParams(searchParams);
    if (value === "all") next.delete("category"); else next.set("category", value);
    setSearchParams(next, { replace: true });
  };
  const applyPrice = (event) => {
    event.preventDefault();
    const next = new URLSearchParams(searchParams);
    if (minimum) next.set("min_price", minimum); else next.delete("min_price");
    if (maximum) next.set("max_price", maximum); else next.delete("max_price");
    setSearchParams(next, { replace: true });
    setFiltersOpen(false);
  };
  const clearFilters = () => { setMinimum(""); setMaximum(""); setCategory("all"); };

  return (
    <section className="page-container page-section">
      <div className="page-heading"><div><span className="eyebrow">THE COLLECTION</span><h1>Shop all products</h1><p>Well-chosen pieces for everyday work and home.</p></div><span className="result-count">{visibleProducts.length} {visibleProducts.length === 1 ? "item" : "items"}</span></div>
      <button className="button button-outline filter-toggle" type="button" aria-expanded={filtersOpen} aria-controls="product-filters" onClick={() => setFiltersOpen((open) => !open)}>{filtersOpen ? "Close filters" : "Filter and sort"}</button>
      <div className="catalog-layout">
        <aside id="product-filters" className={`filter-panel ${filtersOpen ? "is-open" : ""}`} aria-label="Product filters">
          <div className="filter-heading"><h2>Filters</h2><button className="text-button" type="button" onClick={clearFilters}>Clear all</button></div>
          <label className="form-field" htmlFor="category-filter"><span>Category</span><select id="category-filter" value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <form className="price-filter" onSubmit={applyPrice}><span className="filter-label">Price range</span><div className="price-fields"><label className="sr-only" htmlFor="price-min">Minimum price</label><input id="price-min" type="number" min="0" step="1" inputMode="numeric" placeholder="Min ₹" value={minimum} onChange={(event) => setMinimum(event.target.value)} /><label className="sr-only" htmlFor="price-max">Maximum price</label><input id="price-max" type="number" min="0" step="1" inputMode="numeric" placeholder="Max ₹" value={maximum} onChange={(event) => setMaximum(event.target.value)} /></div><button className="button button-secondary button-small button-wide" type="submit">Apply price</button></form>
          <label className="form-field" htmlFor="sort-products"><span>Sort by</span><select id="sort-products" value={sort} onChange={(event) => setSort(event.target.value)}><option value="popular">Most popular</option><option value="price-low">Price: low to high</option><option value="price-high">Price: high to low</option></select></label>
        </aside>
        <div className="catalog-results">
          {error && <p className="notice notice-error" role="alert">{error}</p>}
          {loading ? <ProductLoading /> : <ProductGrid products={visibleProducts} onAdd={addProduct} />}
        </div>
      </div>
    </section>
  );
}

export function ProductDetailPage() {
  const { productId } = useParams();
  const { addProduct } = useCart();
  const { isAuthenticated } = useSession();
  const navigate = useNavigate();
  const [product, setProduct] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    apiRequest(`/products/${productId}`, { signal: controller.signal })
      .then((data) => { setProduct(data); setQuantity(1); })
      .catch((requestError) => { if (requestError.name !== "AbortError") setError(requestError.message); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [productId]);

  const add = async () => {
    if (!isAuthenticated) return navigate("/login", { state: { from: { pathname: `/products/${productId}` } } });
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await addProduct(product.id, quantity);
      setNotice(`${quantity} ${quantity === 1 ? "item" : "items"} added to your bag.`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <section className="page-container page-section"><div className="skeleton detail-skeleton" aria-label="Loading product" /></section>;
  if (error && !product) return <section className="page-container page-section"><div className="notice notice-error" role="alert">{error}</div><Link className="button button-outline" to="/products">Back to products</Link></section>;
  if (!product) return null;

  return (
    <section className="page-container page-section">
      <Link className="back-link" to="/products">← Back to products</Link>
      <div className="product-detail-layout">
        <div className="detail-image-frame"><img src={productImage(product)} alt={product.name} onError={(event) => { event.currentTarget.src = categoryImages.default; }} /></div>
        <div className="detail-copy"><span className="eyebrow">{product.category}</span><h1>{product.name}</h1><p className="detail-price">{money.format(Number(product.price))}</p><p className="detail-description">{product.description || "A considered everyday essential, selected for its useful details and dependable performance."}</p><div className="detail-facts"><span>Availability<strong>{product.stock > 0 ? `${product.stock} in stock` : "Out of stock"}</strong></span><span>Popularity<strong>{product.popularity}</strong></span></div>
          <div className="detail-buy-row"><label className="form-field quantity-field" htmlFor="product-quantity"><span>Quantity</span><input id="product-quantity" type="number" min="1" max={product.stock} value={quantity} onChange={(event) => setQuantity(Math.min(product.stock || 1, Math.max(1, Number(event.target.value) || 1)))} disabled={product.stock < 1} /></label><button className="button button-primary" type="button" onClick={add} disabled={busy || product.stock < 1}>{busy ? "Adding…" : "Add to bag"}</button></div>
          {error && <p className="notice notice-error" role="alert">{error}</p>}{notice && <p className="notice notice-success" role="status">{notice} <Link to="/cart">View bag</Link></p>}
        </div>
      </div>
    </section>
  );
}
