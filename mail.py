import smtplib
from email.message import EmailMessage
from typing import Tuple, Union


class MailClient:
    """Email client for sending messages via SMTP."""

    def __init__(self, smtp_host: str = 'localhost', smtp_port: int = 25):
        """
        Initialize the mail client with SMTP server details.

        Args:
            smtp_host: The SMTP server hostname or IP address (default: localhost).
            smtp_port: The SMTP server port number (default: 25).
        """
        # SMTP server hostname for sending emails.
        self.smtp_host = smtp_host
        # SMTP server port number (25 for standard, 587 for TLS, 465 for SSL).
        self.smtp_port = smtp_port

    def send_plain(self, to_email: str, from_email: str, subject: str, message: str) -> Tuple[
        bool, Union[None, Exception]]:
        """
        Sends a plain text email via SMTP.
        Returns tuple with success status and optional exception.

        Args:
            to_email: Recipient email address.
            from_email: Sender email address.
            subject: Email subject line.
            message: Plain text email body.

        Returns:
            Tuple of (success: bool, error: Optional[Exception]).
        """
        # Create email message object.
        msg = EmailMessage()
        # Set email body as plain text.
        msg.set_content(message)
        # Set email subject line.
        msg['Subject'] = subject
        # Set sender email address.
        msg['From'] = from_email
        # Set recipient email address.
        msg['To'] = to_email

        try:
            # Connect to SMTP server and send message.
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as s:
                # Send the email message.
                s.send_message(msg)
            # Return success status with no error.
            return True, None
        except Exception as e:
            # Return failure status with exception details.
            return False, e
