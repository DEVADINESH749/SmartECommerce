from decimal import Decimal
import logging
import secrets

from fastapi import (
    FastAPI,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
import models

from schemas import (
    CartAdd,
    CartItemRead,
    CartQuantityUpdate,
    CartRead,
    OrderItemRead,
    OrderRead,
    OrderStatusUpdate,
    OrderSummary,
    NotificationRead,
    NotificationUnreadCount,
    PaymentCreate,
    PaymentCreateRead,
    PaymentRead,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    UserCreate,
    UserLogin,
    Auth0ExchangeRequest,
)
from security import hash_password, verify_password

from auth import (
    create_access_token,
    verify_access_token,
    verify_auth0_token,
    verify_auth0_id_token,
)
from payment_service import (
    InvalidWebhookSignature,
    PaymentConfigurationError,
    PaymentProviderError,
    construct_webhook_event,
    create_payment_intent,
    get_stripe_secret_key,
    get_webhook_secret,
    retrieve_payment_intent,
    stripe_value,
)
from email_service import EmailConfigurationError, EmailDeliveryError, send_email
from email_templates import (
    order_cancelled_email,
    order_created_email,
    order_delivered_email,
    order_processing_email,
    order_shipped_email,
    payment_failed_email,
    payment_success_email,
)
from order_status_service import (
    OrderStatusTransitionError,
    create_notification,
    create_order_status_notification,
    restore_order_stock,
    transition_order_status,
)


logger = logging.getLogger(__name__)


def send_event_email(recipient: str, template: dict, event_name: str):
    try:
        send_email(
            to_email=recipient,
            subject=template['subject'],
            html_body=template['html'],
            text_body=template['text'],
        )
    except EmailConfigurationError:
        logger.warning(
            'Email notification skipped: SMTP configuration unavailable (%s)',
            event_name,
        )
    except EmailDeliveryError:
        logger.warning('Email notification delivery failed (%s)', event_name)
    except Exception:
        logger.warning('Email notification processing failed (%s)', event_name)


# =========================
# DATABASE
# =========================

Base.metadata.create_all(bind=engine)


# =========================
# FASTAPI APP
# =========================

app = FastAPI(title="Smart E-Commerce API")


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# DATABASE DEPENDENCY
# =========================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================
# BEARER SECURITY
# =========================

security = HTTPBearer()


# =========================
# LOCAL JWT AUTHENTICATION
# =========================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    payload = verify_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    return payload


# =========================
# ADMIN ROLE CHECK
# =========================

def require_admin(
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {
        "message": "Smart E-Commerce API is running"
    }


# =========================
# REGISTER
# =========================

@app.post("/register")
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    new_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role="customer",
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user_id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
        "role": new_user.role
    }


# =========================
# LOGIN
# =========================

@app.post("/login")
def login_user(
    user: UserLogin,
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        user.password,
        existing_user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not existing_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )

    access_token = create_access_token({
        "sub": str(existing_user.id),
        "role": existing_user.role
    })

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": existing_user.id,
        "name": existing_user.name,
        "email": existing_user.email,
        "role": existing_user.role
    }


# =========================
# LOCAL JWT PROFILE
# =========================

@app.get("/profile")
def profile(
    current_user: dict = Depends(get_current_user)
):
    return {
        "message": "Protected profile accessed successfully",
        "user_id": current_user["sub"],
        "role": current_user.get("role")
    }


# =========================
# LOCAL JWT ADMIN TEST
# =========================

@app.get("/admin/test")
def admin_test(
    current_user: dict = Depends(require_admin)
):
    return {
        "message": "Admin access successful",
        "user_id": current_user["sub"],
        "role": current_user["role"]
    }


# =========================
# AUTH0 TOKEN TEST
# =========================

@app.get("/auth0-profile")
def auth0_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    payload = verify_auth0_token(token)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid Auth0 token"
        )

    return {
        "message": "Auth0 token verified successfully",
        "user": payload
    }


@app.post("/auth0-exchange")
def auth0_exchange(
    request: Auth0ExchangeRequest,
    db: Session = Depends(get_db)
):
    payload = verify_auth0_id_token(request.id_token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid Auth0 token")

    email = payload.get("email")
    if not isinstance(email, str) or payload.get("email_verified") is not True:
        raise HTTPException(
            status_code=403,
            detail="A verified email is required to use this sign-in method"
        )

    email = email.strip().lower()
    if not email:
        raise HTTPException(status_code=403, detail="A verified email is required")

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        display_name = payload.get("name") or payload.get("nickname") or email.split("@", 1)[0]
        user = models.User(
            name=str(display_name)[:100],
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(48)),
            role="customer",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    access_token = create_access_token({
        "sub": str(user.id),
        "role": "customer"
    })
    return {
        "message": "Sign-in successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": "customer"
    }


# =========================
# PRODUCTS
# =========================

@app.post(
    "/products",
    response_model=ProductRead,
    status_code=201
)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    new_product = models.Product(**product.model_dump())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return new_product


@app.get("/products", response_model=list[ProductRead])
def get_products(db: Session = Depends(get_db)):
    return db.query(models.Product).filter(
        models.Product.is_active.is_(True)
    ).all()


@app.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.is_active.is_(True)
    ).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@app.put("/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id
    ).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    changes = product_update.model_dump(exclude_unset=True)
    non_nullable_fields = {
        "name",
        "category",
        "price",
        "stock",
        "popularity",
        "is_active"
    }
    if any(
        changes[field] is None
        for field in non_nullable_fields.intersection(changes)
    ):
        raise HTTPException(
            status_code=422,
            detail="Required product fields cannot be null"
        )

    for field, value in changes.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return product


@app.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id
    ).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    db.delete(product)
    db.commit()


# =========================
# SHOPPING CART
# =========================

def get_cart_owner(db: Session, current_user: dict):
    try:
        user_id = int(current_user["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticated user"
        )

    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.is_active.is_(True)
    ).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found"
        )

    return user


def serialize_cart_item(cart_item: models.Cart, product: models.Product):
    subtotal = product.price * cart_item.quantity

    return CartItemRead(
        id=cart_item.id,
        product_id=product.id,
        product_name=product.name,
        category=product.category,
        price=product.price,
        quantity=cart_item.quantity,
        subtotal=subtotal
    )


@app.get("/cart", response_model=CartRead)
def get_cart(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    rows = db.query(models.Cart, models.Product).join(
        models.Product,
        models.Product.id == models.Cart.product_id
    ).filter(
        models.Cart.user_id == owner.id
    ).order_by(models.Cart.id).all()

    items = [serialize_cart_item(cart_item, product) for cart_item, product in rows]
    total = sum((item.subtotal for item in items), Decimal("0.00"))

    return CartRead(items=items, total=total)


@app.post(
    "/cart",
    response_model=CartItemRead,
    status_code=status.HTTP_201_CREATED
)
def add_to_cart(
    request: CartAdd,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    product = db.query(models.Product).filter(
        models.Product.id == request.product_id
    ).first()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=400, detail="Product is inactive")

    cart_item = db.query(models.Cart).filter(
        models.Cart.user_id == owner.id,
        models.Cart.product_id == product.id
    ).first()
    quantity = request.quantity + (cart_item.quantity if cart_item else 0)

    if quantity > product.stock:
        raise HTTPException(
            status_code=400,
            detail="Requested quantity exceeds available stock"
        )

    if cart_item is None:
        cart_item = models.Cart(
            user_id=owner.id,
            product_id=product.id,
            quantity=quantity
        )
        db.add(cart_item)
    else:
        cart_item.quantity = quantity

    db.commit()
    db.refresh(cart_item)

    return serialize_cart_item(cart_item, product)


@app.put("/cart/{cart_id}", response_model=CartItemRead)
def update_cart_item(
    cart_id: int,
    request: CartQuantityUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    cart_item = db.query(models.Cart).filter(
        models.Cart.id == cart_id,
        models.Cart.user_id == owner.id
    ).first()

    if cart_item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")

    product = db.query(models.Product).filter(
        models.Product.id == cart_item.product_id
    ).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_active:
        raise HTTPException(status_code=400, detail="Product is inactive")
    if request.quantity > product.stock:
        raise HTTPException(
            status_code=400,
            detail="Requested quantity exceeds available stock"
        )

    cart_item.quantity = request.quantity
    db.commit()
    db.refresh(cart_item)

    return serialize_cart_item(cart_item, product)


@app.delete("/cart/{cart_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_cart_item(
    cart_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    cart_item = db.query(models.Cart).filter(
        models.Cart.id == cart_id,
        models.Cart.user_id == owner.id
    ).first()

    if cart_item is None:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.delete(cart_item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.delete("/cart", status_code=status.HTTP_200_OK)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    db.query(models.Cart).filter(
        models.Cart.user_id == owner.id
    ).delete(synchronize_session=False)
    db.commit()

    return {"message": "Cart cleared"}


# =========================
# ORDERS
# =========================

def serialize_order(order: models.Order, items=None):
    if items is None:
        items = order.items

    return OrderRead(
        id=order.id,
        status=order.status,
        total_amount=order.total_amount,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[OrderItemRead.model_validate(item) for item in items]
    )


def get_order_summaries(db: Session, orders: list[models.Order]):
    if not orders:
        return []

    order_ids = [order.id for order in orders]
    item_counts = dict(
        db.query(
            models.OrderItem.order_id,
            func.sum(models.OrderItem.quantity)
        ).filter(
            models.OrderItem.order_id.in_(order_ids)
        ).group_by(models.OrderItem.order_id).all()
    )

    return [
        OrderSummary(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            created_at=order.created_at,
            item_count=int(item_counts.get(order.id, 0))
        )
        for order in orders
    ]


@app.post("/orders", response_model=OrderRead, status_code=201)
def create_order(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)

    try:
        cart_items = db.query(models.Cart).filter(
            models.Cart.user_id == owner.id
        ).order_by(models.Cart.product_id).with_for_update().all()

        if not cart_items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        product_ids = {item.product_id for item in cart_items}
        products = db.query(models.Product).filter(
            models.Product.id.in_(product_ids)
        ).order_by(models.Product.id).with_for_update().all()
        products_by_id = {product.id: product for product in products}

        total_amount = Decimal("0.00")
        order_items_data = []

        for cart_item in cart_items:
            product = products_by_id.get(cart_item.product_id)
            if product is None:
                raise HTTPException(status_code=404, detail="Product not found")
            if not product.is_active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product {product.id} is inactive"
                )
            if cart_item.quantity > product.stock:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for product {product.id}"
                )

            subtotal = product.price * cart_item.quantity
            total_amount += subtotal
            order_items_data.append((cart_item, product, subtotal))

        order = models.Order(
            user_id=owner.id,
            total_amount=total_amount,
            status="PENDING",
            stock_restored=False
        )
        db.add(order)
        db.flush()

        db.add_all([
            models.OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=cart_item.quantity,
                subtotal=subtotal
            )
            for cart_item, product, subtotal in order_items_data
        ])
        db.flush()

        for cart_item, product, _ in order_items_data:
            product.stock -= cart_item.quantity

        db.query(models.Cart).filter(
            models.Cart.user_id == owner.id
        ).delete(synchronize_session=False)
        create_notification(
            db,
            user_id=owner.id,
            title="Order placed",
            message=f"Your order #{order.id} has been placed successfully.",
            notification_type="ORDER_CREATED",
            event_key=f"order:{order.id}:created"
        )
        db.commit()
        db.refresh(order)

        order_items = db.query(models.OrderItem).filter(
            models.OrderItem.order_id == order.id
        ).order_by(models.OrderItem.id).all()
        send_event_email(
            owner.email,
            order_created_email(owner.name, order.id, order.total_amount),
            "order-created"
        )
        return serialize_order(order, order_items)
    except Exception:
        db.rollback()
        raise


@app.get("/orders", response_model=list[OrderSummary])
def get_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    orders = db.query(models.Order).filter(
        models.Order.user_id == owner.id
    ).order_by(models.Order.created_at.desc(), models.Order.id.desc()).all()

    return get_order_summaries(db, orders)


@app.get("/orders/{order_id}", response_model=OrderRead)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == owner.id
    ).first()

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return serialize_order(order)


@app.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)

    try:
        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.user_id == owner.id
        ).with_for_update().first()

        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.status not in {"PENDING", "CONFIRMED"}:
            raise HTTPException(
                status_code=400,
                detail=f"Order cannot be cancelled while {order.status}"
            )

        restore_order_stock(db, order)
        order.status = "CANCELLED"
        create_order_status_notification(db, order)
        db.commit()
        db.refresh(order)
        send_event_email(
            owner.email,
            order_cancelled_email(owner.name, order.id),
            "order-cancelled"
        )
        return serialize_order(order)
    except OrderStatusTransitionError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except Exception:
        db.rollback()
        raise


@app.get("/admin/orders", response_model=list[OrderSummary])
def get_all_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    orders = db.query(models.Order).order_by(
        models.Order.created_at.desc(),
        models.Order.id.desc()
    ).all()

    return get_order_summaries(db, orders)


@app.get("/admin/orders/{order_id}", response_model=OrderRead)
def get_admin_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id
    ).first()

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return serialize_order(order)


@app.put("/admin/orders/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: int,
    request: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    try:
        order = db.query(models.Order).filter(
            models.Order.id == order_id
        ).with_for_update().first()

        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")

        transition_order_status(db, order, request.status, send_event_email)
        return serialize_order(order)
    except OrderStatusTransitionError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except Exception:
        db.rollback()
        raise


# =========================
# NOTIFICATIONS
# =========================

def require_notification_staff(
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("role") not in {"admin", "staff"}:
        raise HTTPException(status_code=403, detail="Staff access required")

    return current_user


@app.get("/notifications", response_model=list[NotificationRead])
def get_notifications(
    is_read: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    query = db.query(models.Notification).filter(
        models.Notification.user_id == owner.id
    )
    if is_read is not None:
        query = query.filter(models.Notification.is_read.is_(is_read))

    return query.order_by(
        models.Notification.created_at.desc(),
        models.Notification.id.desc()
    ).offset(offset).limit(limit).all()


@app.get("/notifications/unread-count", response_model=NotificationUnreadCount)
def get_unread_notification_count(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    unread_count = db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == owner.id,
        models.Notification.is_read.is_(False)
    ).scalar()

    return NotificationUnreadCount(unread_count=unread_count or 0)


@app.put("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    updated_count = db.query(models.Notification).filter(
        models.Notification.user_id == owner.id,
        models.Notification.is_read.is_(False)
    ).update({models.Notification.is_read: True}, synchronize_session=False)
    db.commit()

    return {"updated_count": updated_count}


@app.put(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead
)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == owner.id
    ).first()

    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@app.get("/admin/notifications", response_model=list[NotificationRead])
def get_all_notifications(
    user_id: int | None = Query(default=None, gt=0),
    is_read: bool | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_notification_staff)
):
    query = db.query(models.Notification)
    if user_id is not None:
        query = query.filter(models.Notification.user_id == user_id)
    if is_read is not None:
        query = query.filter(models.Notification.is_read.is_(is_read))

    return query.order_by(
        models.Notification.created_at.desc(),
        models.Notification.id.desc()
    ).offset(offset).limit(limit).all()


# =========================
# PAYMENTS
# =========================

def payment_response(payment: models.Payment):
    return PaymentRead(
        id=payment.id,
        order_id=payment.order_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        created_at=payment.created_at,
        updated_at=payment.updated_at
    )


def apply_payment_intent_status(
    db: Session,
    payment: models.Payment,
    intent_status: str,
    has_last_payment_error: bool = False
):
    order = db.query(models.Order).filter(
        models.Order.id == payment.order_id
    ).with_for_update().first()

    if intent_status == "succeeded":
        payment.status = "SUCCEEDED"
        if order is not None and order.status != "CANCELLED":
            order.status = "CONFIRMED"
        return

    if payment.status == "SUCCEEDED":
        return

    if intent_status == "canceled":
        payment.status = "CANCELLED"
    elif has_last_payment_error:
        payment.status = "FAILED"
        if order is not None and order.status == "CONFIRMED":
            has_another_successful_payment = db.query(models.Payment.id).filter(
                models.Payment.order_id == payment.order_id,
                models.Payment.id != payment.id,
                models.Payment.status == "SUCCEEDED"
            ).first()
            if not has_another_successful_payment:
                order.status = "PENDING"
    else:
        payment.status = "PENDING"


def payment_intent_state(intent):
    last_payment_error = stripe_value(intent, "last_payment_error")
    return stripe_value(intent, "status", ""), last_payment_error is not None


def payment_http_error(error: Exception):
    if isinstance(error, PaymentConfigurationError):
        return HTTPException(
            status_code=503,
            detail="Stripe test-mode configuration is unavailable"
        )

    return HTTPException(
        status_code=502,
        detail="Payment provider request failed"
    )


@app.post(
    "/payments/create",
    response_model=PaymentCreateRead,
    status_code=status.HTTP_201_CREATED
)
def create_payment(
    request: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    order = db.query(models.Order).filter(
        models.Order.id == request.order_id,
        models.Order.user_id == owner.id
    ).with_for_update().first()

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == "CANCELLED":
        raise HTTPException(status_code=400, detail="Cancelled orders cannot be paid")
    if order.total_amount <= 0:
        raise HTTPException(status_code=400, detail="Order amount must be positive")

    try:
        secret_key = get_stripe_secret_key()
    except PaymentConfigurationError as exc:
        raise payment_http_error(exc) from exc

    successful_payment = db.query(models.Payment.id).filter(
        models.Payment.order_id == order.id,
        models.Payment.user_id == owner.id,
        models.Payment.status == "SUCCEEDED"
    ).first()
    if successful_payment:
        raise HTTPException(status_code=409, detail="Order has already been paid")

    payment = db.query(models.Payment).filter(
        models.Payment.order_id == order.id,
        models.Payment.user_id == owner.id,
        models.Payment.status == "PENDING"
    ).order_by(models.Payment.id.desc()).with_for_update().first()

    if payment and payment.stripe_payment_intent_id:
        try:
            intent = retrieve_payment_intent(
                payment.stripe_payment_intent_id,
                secret_key
            )
        except PaymentProviderError as exc:
            raise payment_http_error(exc) from exc

        intent_status, has_error = payment_intent_state(intent)
        apply_payment_intent_status(db, payment, intent_status, has_error)
        if payment.status == "SUCCEEDED":
            db.commit()
            raise HTTPException(status_code=409, detail="Order has already been paid")
        if payment.status == "PENDING":
            db.commit()
            client_secret = stripe_value(intent, "client_secret")
            if not client_secret:
                raise HTTPException(
                    status_code=502,
                    detail="Payment provider returned an invalid payment session"
                )
            return PaymentCreateRead(
                payment_id=payment.id,
                order_id=order.id,
                amount=payment.amount,
                currency=payment.currency,
                status=payment.status,
                client_secret=client_secret
            )
        db.commit()

    if payment is None or payment.status != "PENDING":
        payment = models.Payment(
            order_id=order.id,
            user_id=owner.id,
            amount=order.total_amount,
            currency="inr",
            status="PENDING"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

    amount_minor = int(payment.amount * 100)
    try:
        intent = create_payment_intent(
            amount=amount_minor,
            currency=payment.currency,
            metadata={
                "payment_id": str(payment.id),
                "order_id": str(order.id),
                "user_id": str(owner.id)
            },
            idempotency_key=f"payment-{payment.id}",
            secret_key=secret_key
        )
        intent_id = stripe_value(intent, "id")
        client_secret = stripe_value(intent, "client_secret")
        if not intent_id or not client_secret:
            raise PaymentProviderError
    except PaymentProviderError as exc:
        payment.status = "FAILED"
        db.commit()
        raise payment_http_error(exc) from exc

    payment.stripe_payment_intent_id = intent_id
    intent_status, has_error = payment_intent_state(intent)
    apply_payment_intent_status(db, payment, intent_status, has_error)
    db.commit()
    db.refresh(payment)

    return PaymentCreateRead(
        payment_id=payment.id,
        order_id=order.id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        client_secret=client_secret
    )


@app.get("/payments/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    owner = get_cart_owner(db, current_user)
    payment = db.query(models.Payment).filter(
        models.Payment.id == payment_id,
        models.Payment.user_id == owner.id
    ).first()

    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if not payment.stripe_payment_intent_id:
        return payment_response(payment)

    try:
        secret_key = get_stripe_secret_key()
        intent = retrieve_payment_intent(
            payment.stripe_payment_intent_id,
            secret_key
        )
    except (PaymentConfigurationError, PaymentProviderError) as exc:
        raise payment_http_error(exc) from exc

    intent_status, has_error = payment_intent_state(intent)
    apply_payment_intent_status(db, payment, intent_status, has_error)
    db.commit()
    db.refresh(payment)

    return payment_response(payment)


@app.post("/payments/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature")
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        webhook_secret = get_webhook_secret()
    except PaymentConfigurationError as exc:
        raise payment_http_error(exc) from exc

    payload = await request.body()
    try:
        event = construct_webhook_event(
            payload,
            stripe_signature,
            webhook_secret
        )
    except InvalidWebhookSignature as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid Stripe webhook signature"
        ) from exc

    event_type = stripe_value(event, "type")
    if event_type not in {
        "payment_intent.succeeded",
        "payment_intent.payment_failed"
    }:
        return {"received": True}

    event_id = stripe_value(event, "id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Invalid Stripe event")

    event_data = stripe_value(event, "data", {})
    intent = stripe_value(event_data, "object", {})
    intent_id = stripe_value(intent, "id")
    if not intent_id:
        raise HTTPException(status_code=400, detail="Invalid Stripe event")

    payment = db.query(models.Payment).filter(
        models.Payment.stripe_payment_intent_id == intent_id
    ).with_for_update().first()
    if payment is None:
        return {"received": True}

    email_recipient = None
    email_template = None
    email_event_name = None
    if event_type == "payment_intent.succeeded":
        was_succeeded = payment.status == "SUCCEEDED"
        apply_payment_intent_status(db, payment, "succeeded")
        if payment.status == "SUCCEEDED":
            create_notification(
                db,
                user_id=payment.user_id,
                title="Payment successful",
                message=f"Payment for order #{payment.order_id} was successful.",
                notification_type="PAYMENT_SUCCESS",
                event_key=f"stripe:{event_id}:payment-success"
            )
            if not was_succeeded:
                customer = db.query(models.User).filter(
                    models.User.id == payment.user_id
                ).first()
                if customer:
                    email_recipient = customer.email
                    email_template = payment_success_email(
                        customer.name,
                        payment.order_id,
                        payment.amount
                    )
                    email_event_name = "payment-success"
    else:
        was_failed = payment.status == "FAILED"
        apply_payment_intent_status(
            db,
            payment,
            "requires_payment_method",
            True
        )
        if payment.status == "FAILED":
            create_notification(
                db,
                user_id=payment.user_id,
                title="Payment failed",
                message=f"Payment for order #{payment.order_id} failed.",
                notification_type="PAYMENT_FAILED",
                event_key=f"stripe:{event_id}:payment-failed"
            )
            if not was_failed:
                customer = db.query(models.User).filter(
                    models.User.id == payment.user_id
                ).first()
                if customer:
                    email_recipient = customer.email
                    email_template = payment_failed_email(
                        customer.name,
                        payment.order_id,
                        payment.amount
                    )
                    email_event_name = "payment-failed"

    db.commit()
    if email_recipient and email_template and email_event_name:
        send_event_email(email_recipient, email_template, email_event_name)
    return {"received": True}