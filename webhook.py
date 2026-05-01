from datetime import datetime, timezone
from typing import Tuple, Union, List

import requests


class WebhookClient:
    """Webhook client for posting notifications to external services.

    Supports multiple webhook URLs for flexibility and redundancy.
    Posts JSON-formatted data with check results.
    """

    def __init__(self, webhook_urls: List[str] = None, timeout: int = 10, logger=None):
        """
        Initialize the webhook client with a list of webhook URLs.

        Args:
            webhook_urls: List of webhook URLs to post to.
            timeout: Timeout in seconds for webhook requests (default: 10).
            logger: Optional logger instance for debug and error logging.
        """
        # List of webhook URLs to post notifications to.
        self.webhook_urls = webhook_urls or []
        # Timeout for webhook HTTP requests.
        self.timeout = timeout
        # Logger instance for webhook operations.
        self.logger = logger

        # Log initialization details if logger is available.
        if self.logger:
            self.logger.log_debug(f"WebhookClient initialized with {len(self.webhook_urls)} webhook URL(s), timeout: {self.timeout}s")
            if self.webhook_urls:
                for idx, url in enumerate(self.webhook_urls, 1):
                    self.logger.log_debug(f"  Webhook {idx}: {url}")

    # Maximum number of IP section blocks before truncation (Slack limit is 50 blocks total).
    MAX_IP_BLOCKS = 45

    def _build_blocks_payload(self, data: dict = None) -> dict:
        """
        Build a Slack Block Kit payload for the notification.

        Args:
            data: Dictionary with 'ips' (dict of ip->servers) and 'count' (int).

        Returns:
            Dict with 'text' (fallback) and 'blocks' (Block Kit array).
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "DNS RBL Alert",
                    "emoji": True
                }
            }
        ]

        if data:
            ips = data.get("ips", {})
            count = data.get("count", 0)

            fallback_text = f":rotating_light: DNS RBL Alert - {count} IP(s) listed"

            blocks.append({
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Listed IPs:*\n{count}"}
                ]
            })
            blocks.append({"type": "divider"})

            if ips:
                ip_items = list(ips.items())
                display_items = ip_items[:self.MAX_IP_BLOCKS]
                overflow = len(ip_items) - self.MAX_IP_BLOCKS

                for ip, servers in display_items:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":warning: *{ip}*\n{', '.join(servers)}"
                        }
                    })

                if overflow > 0:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":warning: *...and {overflow} more IP(s) not shown*"
                        }
                    })
            else:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "No listed IPs found."
                    }
                })
        else:
            fallback_text = "DNS RBL Alert - No alert data available"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "No alert data available."
                }
            })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Detected at {timestamp} UTC"
                }
            ]
        })

        return {"text": fallback_text, "blocks": blocks}

    def send_notification(self, data: dict = None) -> Tuple[bool, Union[None, List[str]]]:
        """
        Send a notification to all configured webhooks.
        Posts formatted data as JSON to each webhook.

        Args:
            data: Dictionary with IPs and server data.

        Returns:
            Tuple of (success: bool, errors: Optional[List[str]]).
            Returns (True, None) if all webhooks succeeded.
            Returns (False, [error_messages]) if any webhooks failed.
        """
        # Skip if no webhooks configured.
        if not self.webhook_urls:
            if self.logger:
                self.logger.log_debug("No webhooks configured, skipping webhook notification.")
            return True, None

        # List to collect error messages from failed requests.
        errors = []

        # Build Block Kit payload with structured blocks.
        payload = self._build_blocks_payload(data)

        if self.logger:
            self.logger.log_debug(f"Preparing to send webhook notifications to {len(self.webhook_urls)} URL(s)")
            self.logger.log_debug(f"Notification payload: {len(payload.get('blocks', []))} blocks")

        # Send to each configured webhook.
        for webhook_url in self.webhook_urls:
            try:
                if self.logger:
                    self.logger.log_debug(f"Sending webhook notification to: {webhook_url}")

                # Post JSON data to the webhook URL.
                response = requests.post(
                    webhook_url,
                    json=payload,
                    timeout=self.timeout
                )

                if self.logger:
                    self.logger.log_debug(f"Webhook response status: {response.status_code} from {webhook_url}")

                # Raise exception if HTTP status is not successful.
                response.raise_for_status()

                if self.logger:
                    self.logger.log_info(f"Webhook notification sent successfully to {webhook_url}")

            except requests.exceptions.Timeout:
                # Capture timeout errors.
                error_msg = f"Webhook timeout ({self.timeout}s): {webhook_url}"
                errors.append(error_msg)
                if self.logger:
                    self.logger.log_warn(error_msg)

            except requests.exceptions.ConnectionError as e:
                # Capture connection errors.
                error_msg = f"Webhook connection error: {webhook_url} - {str(e)}"
                errors.append(error_msg)
                if self.logger:
                    self.logger.log_warn(error_msg)

            except requests.exceptions.HTTPError as e:
                # Capture HTTP errors (non-2xx responses).
                error_msg = f"Webhook HTTP error ({e.response.status_code}): {webhook_url} - {str(e)}"
                errors.append(error_msg)
                if self.logger:
                    self.logger.log_warn(error_msg)

            except Exception as e:
                # Capture any other exceptions.
                error_msg = f"Webhook error: {webhook_url} - {str(e)}"
                errors.append(error_msg)
                if self.logger:
                    self.logger.log_error(f"{error_msg}")

        # Log final result
        if self.logger:
            if errors:
                self.logger.log_warn(f"Webhook notification completed with {len(errors)} error(s)")
            else:
                self.logger.log_info(f"All {len(self.webhook_urls)} webhook notification(s) sent successfully")

        # Return success status and errors list (None if no errors).
        return (len(errors) == 0, errors if errors else None)
