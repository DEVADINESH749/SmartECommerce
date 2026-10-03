import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv


load_dotenv()


class EmailConfigurationError(Exception):
    pass


class EmailDeliveryError(Exception):
    pass


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None
):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
    from_name = os.getenv("SMTP_FROM_NAME", "Smart E-Commerce").strip()

    if not smtp_host or not from_email or not to_email or not subject:
        raise EmailConfigurationError("SMTP configuration is incomplete")

    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        raise EmailConfigurationError("SMTP port is invalid") from None

    if not 1 <= smtp_port <= 65535:
        raise EmailConfigurationError("SMTP port is invalid")

    tls_setting = os.getenv("SMTP_USE_TLS", "true").strip().lower()
    if tls_setting not in {"true", "false"}:
        raise EmailConfigurationError("SMTP TLS setting is invalid")

    if bool(smtp_username) != bool(smtp_password):
        raise EmailConfigurationError("SMTP authentication settings are incomplete")

    message = EmailMessage()
    message["From"] = formataddr((from_name, from_email))
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body or "This message is available in HTML format.")
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
            if tls_setting == "true":
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if smtp_username:
                smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
    except Exception:
        raise EmailDeliveryError("Email delivery failed") from None
