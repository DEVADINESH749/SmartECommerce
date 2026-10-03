import logging

import models
from email_service import EmailConfigurationError, EmailDeliveryError, send_email
from email_templates import (
    order_cancelled_email,
    order_delivered_email,
    order_processing_email,
    order_shipped_email,
)


logger = logging.getLogger(__name__)


class OrderStatusTransitionError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def create_notification(
    db,
    *,
    user_id,
    title,
    message,
    notification_type,
    event_key=None,
):
    if event_key:
        existing = db.query(models.Notification).filter(
            models.Notification.event_key == event_key
        ).first()
        if existing:
            return existing

    notification = models.Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        is_read=False,
        event_key=event_key,
    )
    db.add(notification)
    db.flush()
    return notification


def create_order_status_notification(db, order):
    notification_content = {
        'CONFIRMED': (
            'Order confirmed',
            f'Your order #{order.id} has been confirmed.',
            'ORDER_CONFIRMED',
        ),
        'PROCESSING': (
            'Order processing',
            f'Your order #{order.id} is now being processed.',
            'ORDER_PROCESSING',
        ),
        'SHIPPED': (
            'Order shipped',
            f'Your order #{order.id} has been shipped.',
            'ORDER_SHIPPED',
        ),
        'DELIVERED': (
            'Order delivered',
            f'Your order #{order.id} has been delivered.',
            'ORDER_DELIVERED',
        ),
        'CANCELLED': (
            'Order cancelled',
            f'Your order #{order.id} has been cancelled.',
            'ORDER_CANCELLED',
        ),
    }
    content = notification_content.get(order.status)
    if content:
        title, message, notification_type = content
        create_notification(
            db,
            user_id=order.user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            event_key=f'order:{order.id}:status:{order.status}',
        )


def restore_order_stock(db, order):
    if order.stock_restored:
        return

    items = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == order.id
    ).order_by(models.OrderItem.product_id).all()
    product_ids = {item.product_id for item in items}
    products = db.query(models.Product).filter(
        models.Product.id.in_(product_ids)
    ).order_by(models.Product.id).with_for_update().all()
    products_by_id = {product.id: product for product in products}

    for item in items:
        product = products_by_id.get(item.product_id)
        if product is None:
            raise OrderStatusTransitionError(
                409,
                'An order product is no longer available',
            )
        product.stock += item.quantity

    order.stock_restored = True


def send_event_email(recipient, template, event_name):
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


def transition_order_status(db, order, requested_status, email_sender=send_event_email):
    if order.status == 'CANCELLED' and requested_status != 'CANCELLED':
        raise OrderStatusTransitionError(
            400,
            'Cancelled orders cannot be reopened',
        )

    if requested_status == 'CANCELLED':
        restore_order_stock(db, order)

    status_changed = order.status != requested_status
    order.status = requested_status
    email_template = None
    customer = None

    if status_changed:
        create_order_status_notification(db, order)
        status_email_templates = {
            'PROCESSING': order_processing_email,
            'SHIPPED': order_shipped_email,
            'DELIVERED': order_delivered_email,
            'CANCELLED': order_cancelled_email,
        }
        template_factory = status_email_templates.get(requested_status)
        if template_factory:
            customer = db.query(models.User).filter(
                models.User.id == order.user_id
            ).first()
            if customer:
                email_template = template_factory(customer.name, order.id)

    db.commit()
    db.refresh(order)

    if status_changed and email_template and customer:
        email_sender(
            customer.email,
            email_template,
            f'order-{requested_status.lower()}',
        )
    return order