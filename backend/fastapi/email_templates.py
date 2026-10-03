from decimal import Decimal
from html import escape


def _format_amount(amount: Decimal | int | float | str) -> str:
    return f"{Decimal(str(amount)):.2f}"


def _render_email(customer_name: str, subject: str, paragraphs: list[str]):
    safe_name = escape(customer_name or "Customer")
    safe_subject = escape(subject)
    html_paragraphs = "\n".join(
        f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs
    )
    html_body = (
        "<!doctype html><html><body "
        "style=\"font-family:Arial,sans-serif;color:#24313a;line-height:1.6\">"
        f"<h2 style=\"color:#176b87\">{safe_subject}</h2>"
        f"<p>Hello {safe_name},</p>"
        f"{html_paragraphs}"
        "<p>Thank you for shopping with Smart E-Commerce.</p>"
        "</body></html>"
    )
    text_body = "\n\n".join([
        f"Hello {customer_name or 'Customer'},",
        *paragraphs,
        "Thank you for shopping with Smart E-Commerce."
    ])
    return {"subject": subject, "html": html_body, "text": text_body}


def order_created_email(customer_name, order_id, total_amount):
    subject = f"Your Smart E-Commerce Order #{order_id} Has Been Placed"
    return _render_email(
        customer_name,
        subject,
        [
            f"Your order #{order_id} has been placed successfully.",
            f"Order total: ₹{_format_amount(total_amount)}"
        ]
    )


def payment_success_email(customer_name, order_id, amount):
    subject = f"Payment Successful — Order #{order_id}"
    return _render_email(
        customer_name,
        subject,
        [
            f"Your payment for order #{order_id} was successful.",
            f"Amount paid: ₹{_format_amount(amount)}",
            "Your order has been confirmed."
        ]
    )


def payment_failed_email(customer_name, order_id, amount):
    subject = f"Payment Failed — Order #{order_id}"
    return _render_email(
        customer_name,
        subject,
        [
            f"Your payment for order #{order_id} could not be completed.",
            f"Amount: ₹{_format_amount(amount)}",
            "Please try the payment again."
        ]
    )


def order_processing_email(customer_name, order_id):
    subject = f"Your Order #{order_id} Is Being Processed"
    return _render_email(
        customer_name,
        subject,
        [f"Your order #{order_id} is now being processed."]
    )


def order_shipped_email(customer_name, order_id):
    subject = f"Your Order #{order_id} Has Been Shipped"
    return _render_email(
        customer_name,
        subject,
        [f"Your order #{order_id} has been shipped."]
    )


def order_delivered_email(customer_name, order_id):
    subject = f"Your Order #{order_id} Has Been Delivered"
    return _render_email(
        customer_name,
        subject,
        [f"Your order #{order_id} has been delivered."]
    )


def order_cancelled_email(customer_name, order_id):
    subject = f"Your Order #{order_id} Has Been Cancelled"
    return _render_email(
        customer_name,
        subject,
        [f"Your order #{order_id} has been cancelled."]
    )
