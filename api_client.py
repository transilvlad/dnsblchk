from typing import Optional, Tuple, List

import requests


class ApiClient:
    """Client for fetching IP addresses from an external API.
    
    Supports fetching IP addresses from an external API with optional authentication.
    The API should return a text/plain response with one IP address per line.
    """

    def __init__(self, url: str, auth_type: str = 'none', username: str = '', 
                 password: str = '', bearer_token: str = '', timeout: int = 10, logger=None):
        """
        Initialize the API client.

        Args:
            url: API endpoint URL to fetch IP addresses from.
            auth_type: Authentication type ('none', 'basic', or 'bearer').
            username: Username for basic authentication.
            password: Password for basic authentication.
            bearer_token: Bearer token for bearer authentication.
            timeout: Timeout in seconds for API requests (default: 10).
            logger: Optional logger instance for debug and error logging.
        """
        self.url = url
        self.auth_type = auth_type.lower()
        self.username = username
        self.password = password
        self.bearer_token = bearer_token
        self.timeout = timeout
        self.logger = logger

        if self.logger:
            self.logger.log_debug(f"ApiClient initialized with URL: {self.url}, auth_type: {self.auth_type}, timeout: {self.timeout}s")

    def fetch_ips(self) -> Tuple[bool, Optional[List[str]], Optional[str]]:
        """
        Fetch IP addresses from the configured API endpoint.

        Returns:
            Tuple of (success: bool, ips: Optional[List[str]], error: Optional[str]).
            - success: True if fetch was successful, False otherwise.
            - ips: List of IP addresses if successful, None otherwise.
            - error: Error message if failed, None otherwise.
        """
        try:
            if self.logger:
                self.logger.log_debug(f"Fetching IP addresses from API: {self.url}")

            # Prepare authentication
            auth = None
            headers = {}

            if self.auth_type == 'basic':
                if self.username and self.password:
                    auth = (self.username, self.password)
                    if self.logger:
                        self.logger.log_debug(f"Using basic authentication with username: {self.username}")
                else:
                    error_msg = "Basic auth configured but username or password is missing"
                    if self.logger:
                        self.logger.log_warn(error_msg)
                    return False, None, error_msg

            elif self.auth_type == 'bearer':
                if self.bearer_token:
                    headers['Authorization'] = f'Bearer {self.bearer_token}'
                    if self.logger:
                        self.logger.log_debug("Using bearer token authentication")
                else:
                    error_msg = "Bearer auth configured but token is missing"
                    if self.logger:
                        self.logger.log_warn(error_msg)
                    return False, None, error_msg

            # Make the request
            response = requests.get(
                self.url,
                auth=auth,
                headers=headers,
                timeout=self.timeout
            )

            if self.logger:
                self.logger.log_debug(f"API response status: {response.status_code}")

            # Check for successful status code
            response.raise_for_status()

            # Parse the response
            content = response.text.strip()
            if not content:
                error_msg = "API returned empty response"
                if self.logger:
                    self.logger.log_warn(error_msg)
                return False, None, error_msg

            # Split by lines and filter out empty lines
            ips = [line.strip() for line in content.split('\n') if line.strip()]

            if not ips:
                error_msg = "No IP addresses found in API response"
                if self.logger:
                    self.logger.log_warn(error_msg)
                return False, None, error_msg

            if self.logger:
                self.logger.log_info(f"Successfully fetched {len(ips)} IP address(es) from API")
                self.logger.log_debug(f"Fetched IPs: {ips}")

            return True, ips, None

        except requests.exceptions.Timeout:
            error_msg = f"API request timeout ({self.timeout}s): {self.url}"
            if self.logger:
                self.logger.log_warn(error_msg)
            return False, None, error_msg

        except requests.exceptions.ConnectionError as e:
            error_msg = f"API connection error: {self.url} - {str(e)}"
            if self.logger:
                self.logger.log_warn(error_msg)
            return False, None, error_msg

        except requests.exceptions.HTTPError as e:
            error_msg = f"API HTTP error ({e.response.status_code}): {self.url} - {str(e)}"
            if self.logger:
                self.logger.log_warn(error_msg)
            return False, None, error_msg

        except Exception as e:
            error_msg = f"API error: {self.url} - {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg)
            return False, None, error_msg
