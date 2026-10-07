import smtplib
from email.message import EmailMessage

from app.database import settings


def send_email(to: str, subject: str, body: str) -> None:
    """Send one plain-text email through the configured SMTP server.

    Raises smtplib.SMTPException or OSError if the server cannot be reached or
    refuses the message, which is what the Celery task retries on.

    No TLS or login: this talks to Mailpit, which accepts anything on a private
    network. Pointing it at a real provider would need starttls() and login()."""
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    # timeout: without it a server that accepts the connection and then says
    # nothing would hold a worker process forever.
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.send_message(message)
