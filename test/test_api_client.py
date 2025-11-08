"""Unit tests for the api_client module."""
import pytest
from unittest.mock import Mock, patch

from api_client import ApiClient


class TestApiClient:
    """Test cases for ApiClient class."""

    def test_init_default(self):
        """Test ApiClient initialization with default parameters."""
        client = ApiClient(url="https://example.com/ips")
        assert client.url == "https://example.com/ips"
        assert client.auth_type == "none"
        assert client.username == ""
        assert client.password == ""
        assert client.bearer_token == ""
        assert client.timeout == 10
        assert client.logger is None

    def test_init_with_basic_auth(self):
        """Test ApiClient initialization with basic auth."""
        client = ApiClient(
            url="https://example.com/ips",
            auth_type="basic",
            username="user",
            password="pass",
            timeout=20
        )
        assert client.url == "https://example.com/ips"
        assert client.auth_type == "basic"
        assert client.username == "user"
        assert client.password == "pass"
        assert client.timeout == 20

    def test_init_with_bearer_auth(self):
        """Test ApiClient initialization with bearer auth."""
        client = ApiClient(
            url="https://example.com/ips",
            auth_type="bearer",
            bearer_token="token123",
            timeout=15
        )
        assert client.url == "https://example.com/ips"
        assert client.auth_type == "bearer"
        assert client.bearer_token == "token123"
        assert client.timeout == 15

    def test_init_with_logger(self):
        """Test ApiClient initialization with logger."""
        mock_logger = Mock()
        client = ApiClient(url="https://example.com/ips", logger=mock_logger)
        assert client.logger is mock_logger
        mock_logger.log_debug.assert_called()

    @patch('api_client.requests.get')
    def test_fetch_ips_success_no_auth(self, mock_get):
        """Test successful IP fetch without authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1\n10.0.0.1\n172.16.0.1"
        mock_get.return_value = mock_response

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is True
        assert ips == ["192.168.1.1", "10.0.0.1", "172.16.0.1"]
        assert error is None
        mock_get.assert_called_once_with(
            "https://example.com/ips",
            auth=None,
            headers={},
            timeout=10
        )

    @patch('api_client.requests.get')
    def test_fetch_ips_success_basic_auth(self, mock_get):
        """Test successful IP fetch with basic authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1\n10.0.0.1"
        mock_get.return_value = mock_response

        client = ApiClient(
            url="https://example.com/ips",
            auth_type="basic",
            username="user",
            password="pass"
        )
        success, ips, error = client.fetch_ips()

        assert success is True
        assert ips == ["192.168.1.1", "10.0.0.1"]
        assert error is None
        mock_get.assert_called_once_with(
            "https://example.com/ips",
            auth=("user", "pass"),
            headers={},
            timeout=10
        )

    @patch('api_client.requests.get')
    def test_fetch_ips_success_bearer_auth(self, mock_get):
        """Test successful IP fetch with bearer authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1"
        mock_get.return_value = mock_response

        client = ApiClient(
            url="https://example.com/ips",
            auth_type="bearer",
            bearer_token="token123"
        )
        success, ips, error = client.fetch_ips()

        assert success is True
        assert ips == ["192.168.1.1"]
        assert error is None
        mock_get.assert_called_once_with(
            "https://example.com/ips",
            auth=None,
            headers={"Authorization": "Bearer token123"},
            timeout=10
        )

    @patch('api_client.requests.get')
    def test_fetch_ips_with_whitespace(self, mock_get):
        """Test IP fetch with whitespace handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "  192.168.1.1  \n\n  10.0.0.1\n  \n172.16.0.1  "
        mock_get.return_value = mock_response

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is True
        assert ips == ["192.168.1.1", "10.0.0.1", "172.16.0.1"]
        assert error is None

    @patch('api_client.requests.get')
    def test_fetch_ips_empty_response(self, mock_get):
        """Test IP fetch with empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_get.return_value = mock_response

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "empty response" in error.lower()

    @patch('api_client.requests.get')
    def test_fetch_ips_only_whitespace(self, mock_get):
        """Test IP fetch with only whitespace."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "   \n\n   \n   "
        mock_get.return_value = mock_response

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "empty response" in error.lower()

    @patch('api_client.requests.get')
    def test_fetch_ips_basic_auth_missing_username(self, mock_get):
        """Test IP fetch with basic auth but missing username."""
        client = ApiClient(
            url="https://example.com/ips",
            auth_type="basic",
            username="",
            password="pass"
        )
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "username or password is missing" in error.lower()
        mock_get.assert_not_called()

    @patch('api_client.requests.get')
    def test_fetch_ips_basic_auth_missing_password(self, mock_get):
        """Test IP fetch with basic auth but missing password."""
        client = ApiClient(
            url="https://example.com/ips",
            auth_type="basic",
            username="user",
            password=""
        )
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "username or password is missing" in error.lower()
        mock_get.assert_not_called()

    @patch('api_client.requests.get')
    def test_fetch_ips_bearer_auth_missing_token(self, mock_get):
        """Test IP fetch with bearer auth but missing token."""
        client = ApiClient(
            url="https://example.com/ips",
            auth_type="bearer",
            bearer_token=""
        )
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "token is missing" in error.lower()
        mock_get.assert_not_called()

    @patch('api_client.requests.get')
    def test_fetch_ips_timeout(self, mock_get):
        """Test IP fetch with timeout error."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "timeout" in error.lower()

    @patch('api_client.requests.get')
    def test_fetch_ips_connection_error(self, mock_get):
        """Test IP fetch with connection error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "connection error" in error.lower()

    @patch('api_client.requests.get')
    def test_fetch_ips_http_error(self, mock_get):
        """Test IP fetch with HTTP error."""
        import requests
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "http error" in error.lower()
        assert "404" in error

    @patch('api_client.requests.get')
    def test_fetch_ips_generic_exception(self, mock_get):
        """Test IP fetch with generic exception."""
        mock_get.side_effect = Exception("Unexpected error")

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is False
        assert ips is None
        assert "api error" in error.lower()

    @patch('api_client.requests.get')
    def test_fetch_ips_with_logger(self, mock_get):
        """Test IP fetch with logger."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1"
        mock_get.return_value = mock_response

        mock_logger = Mock()
        client = ApiClient(url="https://example.com/ips", logger=mock_logger)
        success, ips, error = client.fetch_ips()

        assert success is True
        assert ips == ["192.168.1.1"]
        assert error is None
        mock_logger.log_debug.assert_called()
        mock_logger.log_info.assert_called()

    @patch('api_client.requests.get')
    def test_fetch_ips_single_ip(self, mock_get):
        """Test IP fetch with single IP."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1"
        mock_get.return_value = mock_response

        client = ApiClient(url="https://example.com/ips")
        success, ips, error = client.fetch_ips()

        assert success is True
        assert ips == ["192.168.1.1"]
        assert error is None

    @patch('api_client.requests.get')
    def test_fetch_ips_custom_timeout(self, mock_get):
        """Test IP fetch with custom timeout."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "192.168.1.1"
        mock_get.return_value = mock_response

        client = ApiClient(url="https://example.com/ips", timeout=30)
        success, ips, error = client.fetch_ips()

        assert success is True
        mock_get.assert_called_once_with(
            "https://example.com/ips",
            auth=None,
            headers={},
            timeout=30
        )

    def test_auth_type_case_insensitive(self):
        """Test that auth_type is case-insensitive."""
        client1 = ApiClient(url="https://example.com/ips", auth_type="BASIC")
        client2 = ApiClient(url="https://example.com/ips", auth_type="Bearer")
        client3 = ApiClient(url="https://example.com/ips", auth_type="NoNe")

        assert client1.auth_type == "basic"
        assert client2.auth_type == "bearer"
        assert client3.auth_type == "none"
