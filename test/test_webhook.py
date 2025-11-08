from unittest.mock import patch, MagicMock

from webhook import WebhookClient


class TestWebhookClient:
    """Test cases for the WebhookClient class."""

    def test_init_default(self):
        """Test WebhookClient initialization with defaults."""
        client = WebhookClient()
        assert client.webhook_urls == []
        assert client.timeout == 10

    def test_init_with_urls(self):
        """Test WebhookClient initialization with webhook URLs."""
        urls = ["https://example.com/webhook", "https://other.com/notify"]
        client = WebhookClient(webhook_urls=urls)
        assert client.webhook_urls == urls
        assert client.timeout == 10

    def test_init_with_timeout(self):
        """Test WebhookClient initialization with custom timeout."""
        client = WebhookClient(timeout=30)
        assert client.timeout == 30

    def test_send_notification_no_webhooks(self):
        """Test send_notification with no webhooks configured."""
        client = WebhookClient(webhook_urls=[])
        success, errors = client.send_notification()
        assert success is True
        assert errors is None

    @patch('webhook.requests.post')
    def test_send_notification_success(self, mock_post):
        """Test successful webhook notification."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        urls = ["https://example.com/webhook"]
        client = WebhookClient(webhook_urls=urls, timeout=10)

        data = {"ips": {"192.168.1.1": ["server1", "server2"]}, "count": 1}

        success, errors = client.send_notification(data)

        assert success is True
        assert errors is None
        # Verify payload has "text" field
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        assert "text" in payload
        assert "192.168.1.1" in payload["text"]

    @patch('webhook.requests.post')
    def test_send_notification_multiple_webhooks(self, mock_post):
        """Test notification to multiple webhooks."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        urls = [
            "https://example.com/webhook",
            "https://other.com/notify",
            "https://third.com/alert"
        ]
        client = WebhookClient(webhook_urls=urls)

        data = {"ips": {"192.168.1.1": ["server1"]}, "count": 1}
        success, errors = client.send_notification(data)

        assert success is True
        assert errors is None
        assert mock_post.call_count == 3

    @patch('webhook.requests.post')
    def test_send_notification_http_error(self, mock_post):
        """Test webhook notification with HTTP error."""
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")

        urls = ["https://example.com/webhook"]
        client = WebhookClient(webhook_urls=urls)

        data = {"ips": {"192.168.1.1": ["server1"]}, "count": 1}
        success, errors = client.send_notification(data)

        assert success is False
        assert errors is not None
        assert len(errors) == 1
        assert "Webhook error" in errors[0]

    @patch('webhook.requests.post')
    def test_send_notification_timeout(self, mock_post):
        """Test webhook notification with timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        urls = ["https://example.com/webhook"]
        client = WebhookClient(webhook_urls=urls, timeout=5)

        data = {"ips": {"192.168.1.1": ["server1"]}, "count": 1}
        success, errors = client.send_notification(data)

        assert success is False
        assert errors is not None
        assert len(errors) == 1
        assert "timeout" in errors[0].lower()

    @patch('webhook.requests.post')
    def test_send_notification_connection_error(self, mock_post):
        """Test webhook notification with connection error."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        urls = ["https://example.com/webhook"]
        client = WebhookClient(webhook_urls=urls)

        data = {"ips": {"192.168.1.1": ["server1"]}, "count": 1}
        success, errors = client.send_notification(data)

        assert success is False
        assert errors is not None
        assert len(errors) == 1
        assert "connection error" in errors[0].lower()

    @patch('webhook.requests.post')
    def test_send_notification_partial_failure(self, mock_post):
        """Test webhook notification with some webhooks failing."""
        # First call succeeds, second fails, third succeeds
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_fail.raise_for_status.side_effect = Exception("500 Server Error")

        mock_post.side_effect = [
            mock_response_success,
            mock_response_fail,
            mock_response_success
        ]

        urls = [
            "https://example.com/webhook",
            "https://fail.com/webhook",
            "https://other.com/webhook"
        ]
        client = WebhookClient(webhook_urls=urls)

        data = {"ips": {"192.168.1.1": ["server1"]}, "count": 1}
        success, errors = client.send_notification(data)

        assert success is False
        assert errors is not None
        assert len(errors) == 1
        assert "fail.com" in errors[0]

    @patch('webhook.requests.post')
    def test_send_notification_with_data(self, mock_post):
        """Test send_notification includes data in payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        urls = ["https://example.com/webhook"]
        client = WebhookClient(webhook_urls=urls)

        data = {
            "ips": {"192.168.1.1": ["list1"], "192.168.1.2": ["list2", "list3"]},
            "count": 2
        }

        success, errors = client.send_notification(data)

        assert success is True
        # Verify the payload structure
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        assert "text" in payload
        assert "2" in payload["text"]  # count should be in text
        assert "192.168.1.1" in payload["text"]  # IP should be in text

    @patch('webhook.requests.post')
    def test_send_notification_without_data(self, mock_post):
        """Test send_notification works without additional data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        urls = ["https://example.com/webhook"]
        client = WebhookClient(webhook_urls=urls)

        success, errors = client.send_notification()

        assert success is True
        # Verify text field is included
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        assert "text" in payload
        assert "Alert" in payload['text']
