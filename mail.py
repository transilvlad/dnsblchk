import smtplib
from email.message import EmailMessage
from typing import Tuple, Union


class MailClient:
    """Email client for sending messages via SMTP.

    Supports optional SMTP authentication and TLS/SSL encryption.
    """

    def __init__(self, smtp_host: str = 'localhost', smtp_port: int = 25,
                 smtp_user: Union[str, None] = None, smtp_password: Union[str, None] = None,
                 use_tls: bool = False, use_ssl: bool = False):
        """
        Initialize the mail client with SMTP server details and optional auth/security.

        Args:
            smtp_host: The SMTP server hostname or IP address (default: localhost).
            smtp_port: The SMTP server port number (default: 25).
            smtp_user: Optional SMTP username for authentication.
            smtp_password: Optional SMTP password for authentication.
            use_tls: If True, issue STARTTLS after connecting (typical for port 587).
            use_ssl: If True, connect using implicit SSL (typical for port 465). Overrides use_tls if both set.
        """
        # SMTP server hostname for sending emails.
        self.smtp_host = smtp_host
        # SMTP server port number (25 for standard, 587 for TLS, 465 for SSL).
        self.smtp_port = smtp_port
        # Optional credentials for SMTP AUTH.
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        # Encryption flags.
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    def _authenticate(self, server) -> None:
        """Authenticate with the SMTP server if credentials are provided."""
        if self.smtp_user and self.smtp_password:
            server.login(self.smtp_user, self.smtp_password)

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
            # Choose SSL or plain SMTP connection.
            if self.use_ssl:
                smtp_cls = smtplib.SMTP_SSL
            else:
                smtp_cls = smtplib.SMTP

            with smtp_cls(self.smtp_host, self.smtp_port) as s:
                # Upgrade to TLS if requested and not already SSL.
                if self.use_tls and not self.use_ssl:
                    s.starttls()
                # Authenticate if credentials provided.
                self._authenticate(s)
                # Send the email message.
                s.send_message(msg)
            # Return success status with no error.
            return True, None
        except Exception as e:
            # Return failure status with exception details.
            return False, e
