from datetime import datetime, timezone
from typing import Tuple, Union, List

import requests


class WebhookClient:
    """Webhook client for posting notifications to external services.

    Supports multiple webhook URLs for flexibility and redundancy.
    Posts JSON-formatted data with check results.
    """

    def __init__(
        self,
        webhook_urls: List[str] = None,
        timeout: int = 10,
        slack_bot_token: str = '',
        slack_channel_id: str = '',
        logger=None,
    ):
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
        self.slack_bot_token = slack_bot_token
        self.slack_channel_id = slack_channel_id
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

    def _build_blocks_payload(self, data: dict = None, pool_resolver=None) -> dict:
        """
        Build a Slack Block Kit payload for the notification.

        Args:
            data: Either per-category format {"category", "title", "ips"} or
                  legacy format {"ips", "count"}.
            pool_resolver: Optional PoolResolver for IP-to-pool-label lookups.

        Returns:
            Dict with 'text' (fallback) and 'blocks' (Block Kit array).
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "DNS Block List Alert", "emoji": True}
            }
        ]

        if data and "summary" in data:
            summary = data.get("summary", {})
            total_listed_ips = int(summary.get("total_listed_ips", 0))
            total_listed_domains = int(summary.get("total_listed_domains", 0))
            newly_listed_ips = summary.get("newly_listed_ips", [])
            newly_listed_domains = summary.get("newly_listed_domains", [])
            delisted_ips = summary.get("delisted_ips", [])
            delisted_domains = summary.get("delisted_domains", [])
            affected_servers = summary.get("affected_servers", [])

            fallback_text = (
                f"DNS summary: {total_listed_ips} IPs listed, {total_listed_domains} domains listed"
            )

            def _list_line(label: str, items: list):
                if not items:
                    return f"- {label} 0"
                limit = 20
                shown = items[:limit]
                more = len(items) - len(shown)
                joined = ", ".join(shown)
                if more > 0:
                    joined = f"{joined}, +{more} more"
                return f"- {label} {len(items)}: ({joined})"

            summary_text = (
                f":rocket: *Summary: {total_listed_ips} IPs listed, {total_listed_domains} domains listed*\n"
                f"{_list_line('New IP Listings', newly_listed_ips)}\n"
                f"{_list_line('New Domain Listings', newly_listed_domains)}\n"
                f"{_list_line('Delisted IPs', delisted_ips)}\n"
                f"{_list_line('Delisted Domains', delisted_domains)}"
            )
            if affected_servers:
                summary_text += "\n- *Most affected servers:* " + ", ".join(
                    f"{item['server']} ({item['listed_ips']})"
                    for item in affected_servers
                )

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary_text}
            })

        elif data and "category" in data:
            # Per-category format — one message per category (newly/still/delisted).
            title   = data.get("title", "")
            ip_dict = data.get("ips", {})
            count   = len(ip_dict)
            fallback_text = f":rotating_light: {title} — {count} IP(s)"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"{title} ({count} IP(s))"}
            })
            blocks.append({"type": "divider"})

            def _row(ip, servers):
                label = pool_resolver.get_label(ip) if pool_resolver else ''
                label_part = f" `{label}`" if label else ''
                if isinstance(servers, set):
                    servers = sorted(servers)
                return f"*{ip}*{label_part}\n{', '.join(servers)}"

            items = list(ip_dict.items())
            can_show = min(len(items), self.MAX_IP_BLOCKS)
            overflow = len(items) - can_show

            for ip, servers in items[:can_show]:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": _row(ip, servers)}
                })

            if overflow > 0:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":warning: *...and {overflow} more not shown.* See attached CSV for full report."
                    }
                })

        elif data and "ips" in data:
            # Legacy flat format — preserves existing behavior exactly.
            ips   = data.get("ips", {})
            count = data.get("count", 0)
            fallback_text = f":rotating_light: DNS Block List Alert - {count} IP(s) listed"

            blocks.append({
                "type": "section",
                "fields": [{"type": "mrkdwn", "text": f"*Listed IPs:*\n{count}"}]
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
                    "text": {"type": "mrkdwn", "text": "No listed IPs found."}
                })
        else:
            fallback_text = "DNS Block List Alert - No alert data available"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "No alert data available."}
            })

        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Detected at {timestamp} UTC"}]
        })

        return {"text": fallback_text, "blocks": blocks}

    def send_notification(self, data: dict = None, pool_resolver=None) -> Tuple[bool, Union[None, List[str]]]:
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
        payload = self._build_blocks_payload(data, pool_resolver=pool_resolver)

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

    def upload_csv_to_slack(self, csv_path) -> Tuple[bool, Union[None, str]]:
        """Upload a CSV report to Slack as a single file attachment.

        Args:
            csv_path: Path-like pointing to the CSV file to post.

        Returns:
            Tuple (success: bool, error: Optional[str]).
        """
        from pathlib import Path as _Path
        p = _Path(csv_path)
        if not p.exists():
            msg = f"post_csv_via_webhook: file not found: {p}"
            if self.logger:
                self.logger.log_error(msg)
            return False, msg

        if not self.slack_bot_token or not self.slack_channel_id:
            msg = "Slack bot token and channel ID are required for CSV upload"
            if self.logger:
                self.logger.log_error(msg)
            return False, msg

        try:
            content = p.read_bytes()
            headers = {"Authorization": f"Bearer {self.slack_bot_token}"}
            upload_response = requests.post(
                "https://slack.com/api/files.getUploadURLExternal",
                headers=headers,
                data={"filename": p.name, "length": len(content)},
                timeout=self.timeout,
            )
            upload_response.raise_for_status()
            upload_data = upload_response.json()
            if not upload_data.get("ok"):
                return False, f"Slack upload URL request failed: {upload_data.get('error', 'unknown error')}"

            file_response = requests.post(
                upload_data["upload_url"],
                files={"file": (p.name, content, "text/csv")},
                timeout=self.timeout,
            )
            file_response.raise_for_status()

            complete_response = requests.post(
                "https://slack.com/api/files.completeUploadExternal",
                headers=headers,
                data={
                    "files": f'[{{"id":"{upload_data["file_id"]}","title":"{p.stem}"}}]',
                    "channel_id": self.slack_channel_id,
                },
                timeout=self.timeout,
            )
            complete_response.raise_for_status()
            complete_data = complete_response.json()
            if not complete_data.get("ok"):
                return False, f"Slack file completion failed: {complete_data.get('error', 'unknown error')}"

            if self.logger:
                self.logger.log_info(f"Uploaded {p.name} ({len(content)} bytes) to Slack")
            return True, None
        except (requests.RequestException, ValueError, KeyError) as e:
            msg = f"Slack CSV upload failed: {e}"
            if self.logger:
                self.logger.log_error(msg)
            return False, msg
