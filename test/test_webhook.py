from datetime import datetime
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
        # Verify Block Kit payload structure
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        assert "text" in payload
        assert "blocks" in payload
        assert payload["blocks"][0]["type"] == "header"
        # Verify IP appears in a section block
        block_texts = [b.get("text", {}).get("text", "") for b in payload["blocks"] if b.get("type") == "section" and "text" in b]
        assert any("192.168.1.1" in t for t in block_texts)

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
        # Verify Block Kit payload structure
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        assert "text" in payload
        assert "2" in payload["text"]  # count should be in fallback text
        assert "blocks" in payload
        # Verify count appears in section fields
        section_fields = [b for b in payload["blocks"] if b.get("type") == "section" and "fields" in b]
        assert len(section_fields) == 1
        assert "2" in section_fields[0]["fields"][0]["text"]
        # Verify both IPs appear in section blocks
        block_texts = [b.get("text", {}).get("text", "") for b in payload["blocks"] if b.get("type") == "section" and "text" in b]
        assert any("192.168.1.1" in t for t in block_texts)
        assert any("192.168.1.2" in t for t in block_texts)

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
        # Verify Block Kit payload
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']
        assert "text" in payload
        assert "Alert" in payload['text']
        assert "blocks" in payload
        assert payload["blocks"][0]["type"] == "header"
        assert payload["blocks"][0]["text"]["text"] == "DNS RBL Alert"

    def test_build_blocks_payload_structure(self):
        """Test _build_blocks_payload returns correct Block Kit structure."""
        client = WebhookClient(webhook_urls=["https://example.com/webhook"])
        data = {"ips": {"10.0.0.1": ["rbl1", "rbl2"], "10.0.0.2": ["rbl3"]}, "count": 2}

        payload = client._build_blocks_payload(data)

        assert "text" in payload
        assert "blocks" in payload
        blocks = payload["blocks"]
        # Header, section with fields, divider, 2 IP sections, context = 6 blocks
        assert len(blocks) == 6
        assert blocks[0]["type"] == "header"
        assert blocks[0]["text"]["text"] == "DNS RBL Alert"
        assert blocks[1]["type"] == "section"
        assert blocks[1]["fields"][0]["text"] == "*Listed IPs:*\n2"
        assert blocks[2]["type"] == "divider"
        assert blocks[3]["type"] == "section"
        assert "10.0.0.1" in blocks[3]["text"]["text"]
        assert "rbl1, rbl2" in blocks[3]["text"]["text"]
        assert blocks[4]["type"] == "section"
        assert "10.0.0.2" in blocks[4]["text"]["text"]
        assert blocks[5]["type"] == "context"
        assert "Detected at" in blocks[5]["elements"][0]["text"]

    def test_build_blocks_payload_no_data(self):
        """Test _build_blocks_payload with None data."""
        client = WebhookClient(webhook_urls=["https://example.com/webhook"])

        payload = client._build_blocks_payload(None)

        assert "Alert" in payload["text"]
        blocks = payload["blocks"]
        # Header, "no data" section, context = 3 blocks
        assert len(blocks) == 3
        assert blocks[0]["type"] == "header"
        assert blocks[1]["type"] == "section"
        assert "No alert data available" in blocks[1]["text"]["text"]
        assert blocks[2]["type"] == "context"

    def test_build_blocks_payload_empty_ips(self):
        """Test _build_blocks_payload with empty ips dict."""
        client = WebhookClient(webhook_urls=["https://example.com/webhook"])
        data = {"ips": {}, "count": 0}

        payload = client._build_blocks_payload(data)

        blocks = payload["blocks"]
        # Header, section with fields, divider, "no listed IPs" section, context = 5 blocks
        assert len(blocks) == 5
        section_texts = [b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b]
        assert any("No listed IPs found" in t for t in section_texts)

    def test_build_blocks_payload_many_ips(self):
        """Test _build_blocks_payload truncates beyond MAX_IP_BLOCKS."""
        client = WebhookClient(webhook_urls=["https://example.com/webhook"])
        # Create 50 IPs (exceeds MAX_IP_BLOCKS=45)
        ips = {f"10.0.0.{i}": [f"rbl{i}"] for i in range(50)}
        data = {"ips": ips, "count": 50}

        payload = client._build_blocks_payload(data)

        blocks = payload["blocks"]
        # Should not exceed 50 total blocks
        assert len(blocks) <= 50
        # Should have an overflow indicator
        all_text = " ".join(
            b.get("text", {}).get("text", "") for b in blocks if b.get("type") == "section"
        )
        assert "more IP(s) not shown" in all_text

    @patch('webhook.datetime')
    def test_build_blocks_payload_timestamp(self, mock_datetime):
        """Test _build_blocks_payload includes correct UTC timestamp."""
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-01-15 10:30:00"
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        client = WebhookClient(webhook_urls=["https://example.com/webhook"])
        data = {"ips": {"10.0.0.1": ["rbl1"]}, "count": 1}

        payload = client._build_blocks_payload(data)

        context_block = [b for b in payload["blocks"] if b.get("type") == "context"][0]
        assert "2026-01-15 10:30:00 UTC" in context_block["elements"][0]["text"]
