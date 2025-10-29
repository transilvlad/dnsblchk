from unittest.mock import patch, MagicMock

from mail import MailClient


class TestMailClient:
    """Test cases for MailClient class."""

    def test_mail_client_initialization_defaults(self):
        """Test MailClient initialization with default values."""
        client = MailClient()
        assert client.smtp_host == 'localhost'
        assert client.smtp_port == 25

    def test_mail_client_initialization_custom(self):
        """Test MailClient initialization with custom values."""
        client = MailClient(smtp_host='mail.example.com', smtp_port=587)
        assert client.smtp_host == 'mail.example.com'
        assert client.smtp_port == 587

    @patch('mail.smtplib.SMTP')
    def test_send_plain_success(self, mock_smtp):
        """Test successful sending of plain text email."""
        client = MailClient(smtp_host='localhost', smtp_port=25)

        # Mock the SMTP connection
        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        success, error = client.send_plain(
            to_email='test@example.com',
            from_email='sender@example.com',
            subject='Test Subject',
            message='Test message body'
        )

        assert success is True
        assert error is None
        mock_connection.send_message.assert_called_once()

    @patch('mail.smtplib.SMTP')
    def test_send_plain_connection_error(self, mock_smtp):
        """Test sending email with connection error."""
        client = MailClient()

        # Mock SMTP to raise an exception
        mock_smtp.side_effect = ConnectionError("Connection refused")

        success, error = client.send_plain(
            to_email='test@example.com',
            from_email='sender@example.com',
            subject='Test Subject',
            message='Test message body'
        )

        assert success is False
        assert error is not None
        assert isinstance(error, ConnectionError)

    @patch('mail.smtplib.SMTP')
    def test_send_plain_creates_correct_message(self, mock_smtp):
        """Test that send_plain creates correct email message."""
        client = MailClient()

        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        client.send_plain(
            to_email='recipient@example.com',
            from_email='sender@example.com',
            subject='Subject Line',
            message='Message Body'
        )

        # Get the message that was sent
        call_args = mock_connection.send_message.call_args
        message = call_args[0][0]

        # Verify message properties
        assert message['Subject'] == 'Subject Line'
        assert message['From'] == 'sender@example.com'
        assert message['To'] == 'recipient@example.com'

    @patch('mail.smtplib.SMTP')
    def test_send_plain_with_special_characters(self, mock_smtp):
        """Test sending email with special characters."""
        client = MailClient()

        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        success, error = client.send_plain(
            to_email='test+tag@example.com',
            from_email='sender@example.com',
            subject='Subject with émojis ���',
            message='Message with special chars: @#$%^&*()'
        )

        assert success is True
        assert error is None

    @patch('mail.smtplib.SMTP')
    def test_send_plain_multiple_recipients(self, mock_smtp):
        """Test that send_plain sends to correct recipient."""
        client = MailClient()

        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        # Send to first recipient
        client.send_plain(
            to_email='recipient1@example.com',
            from_email='sender@example.com',
            subject='Test',
            message='Test'
        )

        call_args1 = mock_connection.send_message.call_args[0][0]
        assert call_args1['To'] == 'recipient1@example.com'

        # Send to second recipient
        mock_connection.reset_mock()
        client.send_plain(
            to_email='recipient2@example.com',
            from_email='sender@example.com',
            subject='Test',
            message='Test'
        )

        call_args2 = mock_connection.send_message.call_args[0][0]
        assert call_args2['To'] == 'recipient2@example.com'

    @patch('mail.smtplib.SMTP')
    def test_send_plain_empty_message(self, mock_smtp):
        """Test sending email with empty message body."""
        client = MailClient()

        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        success, error = client.send_plain(
            to_email='test@example.com',
            from_email='sender@example.com',
            subject='Empty Message',
            message=''
        )

        assert success is True
        assert error is None

    @patch('mail.smtplib.SMTP')
    def test_send_plain_long_message(self, mock_smtp):
        """Test sending email with very long message."""
        client = MailClient()

        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        long_message = 'A' * 10000
        success, error = client.send_plain(
            to_email='test@example.com',
            from_email='sender@example.com',
            subject='Long Message',
            message=long_message
        )

        assert success is True
        assert error is None

    @patch('mail.smtplib.SMTP')
    def test_send_plain_uses_correct_host_port(self, mock_smtp):
        """Test that send_plain connects to correct host and port."""
        client = MailClient(smtp_host='mail.server.com', smtp_port=587)

        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        client.send_plain(
            to_email='test@example.com',
            from_email='sender@example.com',
            subject='Test',
            message='Test'
        )

        mock_smtp.assert_called_once_with('mail.server.com', 587)

    @patch('mail.smtplib.SMTP')
    def test_send_plain_smtp_timeout(self, mock_smtp):
        """Test handling of SMTP timeout exception."""
        client = MailClient()

        import socket
        mock_smtp.side_effect = socket.timeout("Connection timeout")

        success, error = client.send_plain(
            to_email='test@example.com',
            from_email='sender@example.com',
            subject='Test',
            message='Test'
        )

        assert success is False
        assert error is not None

    @patch('mail.smtplib.SMTP')
    def test_send_plain_returns_tuple(self, mock_smtp):
        """Test that send_plain returns a tuple."""
        client = MailClient()

        mock_connection = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_connection

        result = client.send_plain(
            to_email='test@example.com',
            from_email='sender@example.com',
            subject='Test',
            message='Test'
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)

    # New tests for authentication and encryption
    @patch('mail.smtplib.SMTP')
    def test_send_plain_with_authentication(self, mock_smtp):
        """Test SMTP authentication occurs when username/password provided."""
        client = MailClient(smtp_host='localhost', smtp_port=587, smtp_user='user', smtp_password='pass')
        mock_conn = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_conn

        client.send_plain('to@example.com', 'from@example.com', 'Subject', 'Body')

        mock_conn.login.assert_called_once_with('user', 'pass')

    @patch('mail.smtplib.SMTP')
    def test_send_plain_without_authentication(self, mock_smtp):
        """Test SMTP authentication does not occur when credentials missing."""
        client = MailClient(smtp_host='localhost', smtp_port=587)
        mock_conn = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_conn

        client.send_plain('to@example.com', 'from@example.com', 'Subject', 'Body')

        mock_conn.login.assert_not_called()

    @patch('mail.smtplib.SMTP')
    def test_send_plain_with_starttls(self, mock_smtp):
        """Test STARTTLS is invoked when use_tls is True and use_ssl is False."""
        client = MailClient(smtp_host='localhost', smtp_port=587, use_tls=True, use_ssl=False)
        mock_conn = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_conn

        client.send_plain('to@example.com', 'from@example.com', 'Subject', 'Body')

        mock_conn.starttls.assert_called_once()

    @patch('mail.smtplib.SMTP_SSL')
    def test_send_plain_with_ssl(self, mock_smtp_ssl):
        """Test implicit SSL connection when use_ssl is True."""
        client = MailClient(smtp_host='localhost', smtp_port=465, use_tls=True, use_ssl=True)
        mock_conn = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_conn

        client.send_plain('to@example.com', 'from@example.com', 'Subject', 'Body')

        # STARTTLS should not be called when SSL is used
        mock_conn.starttls.assert_not_called()
        mock_smtp_ssl.assert_called_once_with('localhost', 465)

"""Test suite for DNSBL Checker application."""
