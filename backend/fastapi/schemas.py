from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Auth0ExchangeRequest(BaseModel):
    id_token: str = Field(min_length=1)


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    popularity: int = Field(default=0, ge=0)
    image: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2
    )
    stock: int | None = Field(default=None, ge=0)
    popularity: int | None = Field(default=None, ge=0)
    image: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    category: str
    price: Decimal
    stock: int
    popularity: int
    image: str | None
    is_active: bool
    created_at: datetime


class CartAdd(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class CartQuantityUpdate(BaseModel):
    quantity: int = Field(gt=0)


class CartItemRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    category: str
    price: Decimal
    quantity: int
    subtotal: Decimal


class CartRead(BaseModel):
    items: list[CartItemRead]
    total: Decimal


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal


class OrderRead(BaseModel):
    id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderSummary(BaseModel):
    id: int
    status: str
    total_amount: Decimal
    created_at: datetime
    item_count: int


class OrderStatusUpdate(BaseModel):
    status: str = Field(
        pattern="^(PENDING|CONFIRMED|PROCESSING|SHIPPED|DELIVERED|CANCELLED)$"
    )


class PaymentCreate(BaseModel):
    order_id: int = Field(gt=0)


class PaymentCreateRead(BaseModel):
    payment_id: int
    order_id: int
    amount: Decimal
    currency: str
    status: str
    client_secret: str


class PaymentRead(BaseModel):
    id: int
    order_id: int
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime


class NotificationUnreadCount(BaseModel):
    unread_count: int