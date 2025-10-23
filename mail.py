import smtplib
from email.message import EmailMessage
from typing import Tuple, Union


class MailClient:
    """Email client for sending messages via SMTP."""

    def __init__(self, smtp_host: str = 'localhost', smtp_port: int = 25):
        """Initialize the mail client with SMTP server details."""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    def send_plain(self, to_email: str, from_email: str, subject: str, message: str) -> Tuple[
        bool, Union[None, Exception]]:
        """Sends a plain text email."""
        msg = EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as s:
                s.send_message(msg)
            return True, None
        except Exception as e:
            return False, e
