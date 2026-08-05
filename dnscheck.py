import csv
import ipaddress
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import Lock
from typing import Optional

from config import config
from domaincheck import DomainResolver
from logger import Logger, LogConfig, LogLevel
from mail import MailClient
from rblcheck import RBLCheck
from signals import SignalHandler
from webhook import WebhookClient


class DNSCheck:
    """
    Handles DNS RBL and DBL checking with support for multithreading.
    Manages check coordination, result reporting, and notifications.
    """

    def __init__(self, mail_client: MailClient, dnsrbl_checker: RBLCheck, logger: Logger, webhook_client: WebhookClient = None):
        """
        Initialize the DNS block list check handler.

        Args:
            mail_client: MailClient instance for sending alerts.
            dnsrbl_checker: DNS block list checker instance for RBL/DBL queries.
            logger: Logger instance for logging.
            webhook_client: WebhookClient instance for sending webhook notifications (optional).
        """
        # Mail client for sending email alerts on listed IPs.
        self.mail_client = mail_client
        # Webhook client for posting notifications to external services.
        self.webhook_client = webhook_client
        # DNS RBL/DBL Checker instance for performing block list queries.
        self.dnsrbl_checker = dnsrbl_checker
        # Domain resolver for PTR/apex target derivation used by DBL checks.
        self.domain_resolver = DomainResolver(config.get_nameservers())
        # Logger instance for recording check results and errors.
        self.logger = logger
        # Dictionary mapping IPs to list of servers they're listed on.
        self.listed_ips = {}
        # File handle for CSV report file.
        self.report_file_handler = None
        # CSV writer instance for writing results to report file.
        self.csv_writer = None
        # Lock for thread-safe file writing and IP recording.
        self.lock = Lock()

    def check_ip_against_server(self, ip: str, server: str) -> tuple:
        """
        Check a single IP against a single DNS RBL server.
        This method is executed by worker threads in the thread pool.

        Args:
            ip: The IP address to check.
            server: The DNS RBL server to check against.

        Returns:
            tuple: (ip, server, is_listed, result_details) or None if shutdown requested or error.
        """
        # Return early if shutdown has been requested.
        if SignalHandler().is_shutdown_requested:
            return None

        try:
            # Query DNS RBL server for the IP address.
            is_listed = self.dnsrbl_checker.check(ip, server)
            # Extract result details from response (if listed).
            return (ip, server, is_listed, is_listed[1] if is_listed else None)
        except Exception as e:
            # Log error but don't fail the entire check run.
            self.logger.log_error(f"Error checking {ip} against {server}: {str(e)}")
            return None

    def check_domain_against_server(self, source_ip: str, domain: str, domain_source: str, server: str) -> tuple:
        """
        Check a single domain target against a single DNS DBL server.

        Args:
            source_ip: The original IP from which the domain target was derived.
            domain: Domain target (PTR hostname or apex).
            domain_source: Origin of the domain target ('ptr' or 'apex').
            server: The DNS DBL server to check against.

        Returns:
            tuple: (source_ip, domain, domain_source, server, is_listed, response_code, txt_context)
                or None if shutdown requested or error.
        """
        if SignalHandler().is_shutdown_requested:
            return None

        try:
            is_listed = self.dnsrbl_checker.check_domain(domain, server)
            response_code = is_listed[1] if is_listed and len(is_listed) > 1 else None
            txt_context = ''
            if is_listed:
                txt_entries = [entry for entry in is_listed if isinstance(entry, str) and entry.startswith("TXT=")]
                if txt_entries:
                    txt_context = txt_entries[0][4:]
            return (source_ip, domain, domain_source, server, is_listed, response_code, txt_context)
        except Exception as e:
            self.logger.log_error(f"Error checking {domain} ({domain_source}) against {server}: {str(e)}")
            return None

    def derive_domain_targets_for_ip(self, ip: str) -> tuple:
        """
        Derive DBL domain targets for an IP address.

        Returns:
            tuple: (ip, set of (domain, source) tuples) or an empty set on error.
        """
        if SignalHandler().is_shutdown_requested:
            return (ip, set())

        try:
            return (ip, self.domain_resolver.derive_check_targets(ip))
        except Exception as e:
            self.logger.log_error(f"Error deriving domain targets for {ip}: {str(e)}")
            return (ip, set())

    def _write_report(
        self,
        ip: str,
        server: str,
        result_details: str,
        check_type: str = 'rbl',
        target: Optional[str] = None,
        target_source: str = 'ip',
        txt_context: str = ''
    ):
        """
        Write a report entry to the CSV file (thread-safe).
        Lazily initializes the report file on first write.

        Args:
            ip: The source IP address.
            server: The DNS block list server.
            result_details: Details about the listing.
            check_type: RBL/DBL check type.
            target: Actual IP/domain target queried.
            target_source: Target origin: ip, ptr, or apex.
            txt_context: Optional TXT response context from DBL.
        """
        # Use lock to ensure thread-safe file operations.
        with self.lock:
            # Create report file on first write (lazy initialization).
            if self.report_file_handler is None:
                # Generate timestamp-based filename for report.
                timestamp_filename = time.strftime("%Y%m%d%H%M%S", time.gmtime())
                # Construct full path to report file.
                report_file_path = config.report_dir / f"report_{timestamp_filename}.csv"
                # Open report file for writing.
                self.report_file_handler = open(report_file_path, 'w', newline='')
                # Create CSV writer instance.
                self.csv_writer = csv.writer(self.report_file_handler)
                # Write header for sortable/structured reports.
                self.csv_writer.writerow([
                    "timestamp",
                    "source_ip",
                    "check_type",
                    "target",
                    "target_source",
                    "server",
                    "obm_server",
                    "response",
                    "txt_context",
                ])

            # Format current timestamp for report entry.
            timestamp = time.strftime("%d %b %Y %H:%M:%S", time.gmtime())
            if target is None:
                target = ip
            check_type = self._report_check_type(check_type, target_source)
            address_group = self._get_address_group(ip)
            self.csv_writer.writerow([
                timestamp,
                ip,
                check_type,
                target,
                target_source,
                server,
                address_group,
                result_details or '',
                txt_context or '',
            ])
            # Flush to ensure data is written immediately.
            self.report_file_handler.flush()

    def _record_listed_ip(self, ip: str, server_label: str):
        """
        Record a listed IP (thread-safe).
        Maintains a dictionary of listed IPs and their corresponding servers.

        Args:
            ip: The IP address.
            server_label: The DNS block list server label.
        """
        # Use lock to ensure thread-safe dictionary updates.
        with self.lock:
            # Create entry for IP if it doesn't exist.
            if ip not in self.listed_ips:
                self.listed_ips[ip] = []
            # Add server label to IP's list if not already present.
            if server_label not in self.listed_ips[ip]:
                self.listed_ips[ip].append(server_label)

    def _process_check_result(self, result: tuple):
        """
        Process an RBL or DBL check result.
        Updates reports and alerts based on check outcome.

        Args:
            result: RBL tuple or DBL tuple from a worker method.
        """
        # Skip processing if result is None (shutdown or error).
        if result is None:
            return

        # Unpack result tuple components (supports both RBL and DBL result shapes).
        if len(result) == 4:
            ip, server, is_listed, result_details = result
            check_type = 'rbl'
            target = ip
            target_source = 'ip'
            txt_context = ''
        else:
            ip, target, target_source, server, is_listed, result_details, txt_context = result
            check_type = 'dbl'

        # Handle positive listing result.
        if is_listed:
            self._write_report(
                ip=ip,
                server=server,
                result_details=result_details,
                check_type=check_type,
                target=target,
                target_source=target_source,
                txt_context=txt_context,
            )
            if check_type == 'rbl':
                server_label = server
                self.logger.log_info(f"DIRTY: {ip} is listed on {server}")
            else:
                server_label = f"{server} [{target_source}:{target}]"
                self.logger.log_info(
                    f"DIRTY: {ip} domain target {target} ({target_source}) is listed on {server}"
                )
            self._record_listed_ip(ip, server_label)
        else:
            if check_type == 'rbl':
                self.logger.log_debug(f"CLEAN: {ip} is not listed on {server}")
            else:
                self.logger.log_debug(
                    f"CLEAN: {ip} domain target {target} ({target_source}) is not listed on {server}"
                )

    @staticmethod
    def _get_address_group(ip: str) -> str:
        """Return the most specific configured group containing an IP."""
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return ''

        groups = config.get_address_groups()
        if not isinstance(groups, dict):
            return ''

        matches = []
        for label, entries in groups.items():
            if isinstance(entries, str):
                entries = [entries]
            if not isinstance(entries, (list, tuple, set)):
                continue
            for entry in entries:
                try:
                    network = ipaddress.ip_network(str(entry), strict=False)
                except ValueError:
                    continue
                if address in network:
                    matches.append((network.prefixlen, str(label)))
        return max(matches, key=lambda match: (match[0], match[1]))[1] if matches else ''

    @staticmethod
    def _normalized_server_list(raw_servers):
        """Return stripped server names from CSV rows."""
        normalized = []
        for row in raw_servers:
            if not row:
                continue
            server = row[0].strip()
            if server:
                normalized.append(server)
        return normalized

    @staticmethod
    def _normalized_ip_list(raw_ips):
        """Return stripped IP strings from CSV rows."""
        return [row[0].strip() for row in raw_ips if row and row[0].strip()]

    def _run_serial_checks(self, rbl_servers: list, dbl_servers: list, ips: list):
        """Run all checks sequentially."""
        for server in rbl_servers:
            if SignalHandler().is_shutdown_requested:
                return
            for ip in ips:
                if SignalHandler().is_shutdown_requested:
                    return
                self._process_check_result(self.check_ip_against_server(ip, server))

        if dbl_servers:
            for ip in ips:
                if SignalHandler().is_shutdown_requested:
                    return
                _, domain_targets = self.derive_domain_targets_for_ip(ip)
                for domain, domain_source in sorted(domain_targets):
                    if SignalHandler().is_shutdown_requested:
                        return
                    for server in dbl_servers:
                        if SignalHandler().is_shutdown_requested:
                            return
                        self._process_check_result(
                            self.check_domain_against_server(ip, domain, domain_source, server)
                        )

    def _run_threaded_checks(self, rbl_servers: list, dbl_servers: list, ips: list, thread_count: int):
        """Run all checks using a thread pool."""
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {}

            for server in rbl_servers:
                if SignalHandler().is_shutdown_requested:
                    break
                for ip in ips:
                    if SignalHandler().is_shutdown_requested:
                        break
                    future = executor.submit(self.check_ip_against_server, ip, server)
                    futures[future] = ('rbl', ip, server)

            if dbl_servers:
                for ip in ips:
                    if SignalHandler().is_shutdown_requested:
                        break
                    future = executor.submit(self.derive_domain_targets_for_ip, ip)
                    futures[future] = ('derive', ip)

            while futures:
                if SignalHandler().is_shutdown_requested:
                    break

                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    meta = futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as e:
                        if meta[0] == 'rbl':
                            _, ip, server = meta
                            self.logger.log_error(f"Exception checking {ip} against {server}: {str(e)}")
                        elif meta[0] == 'derive':
                            _, ip = meta
                            self.logger.log_error(f"Exception deriving domain targets for {ip}: {str(e)}")
                        else:
                            _, ip, domain, domain_source, server = meta
                            self.logger.log_error(
                                f"Exception checking {ip} domain target {domain} ({domain_source}) against {server}: {str(e)}"
                            )
                        continue

                    if meta[0] == 'derive':
                        ip, domain_targets = result
                        for domain, domain_source in sorted(domain_targets):
                            if SignalHandler().is_shutdown_requested:
                                break
                            for server in dbl_servers:
                                if SignalHandler().is_shutdown_requested:
                                    break
                                dbl_future = executor.submit(
                                    self.check_domain_against_server,
                                    ip,
                                    domain,
                                    domain_source,
                                    server,
                                )
                                futures[dbl_future] = ('dbl', ip, domain, domain_source, server)
                    else:
                        self._process_check_result(result)

                    time.sleep(0.01)

    def run(self, rbl_servers: list, dbl_servers: list, ips: list):
        """
        Run DNS RBL and DBL checks with multithreading support.

        Args:
            rbl_servers: List of DNS RBL servers (each server is a list/tuple).
            dbl_servers: List of DNS DBL servers (each server is a list/tuple).
            ips: List of IPs to check (each IP is a list/tuple).
        """
        # Return early if shutdown has been requested.
        if SignalHandler().is_shutdown_requested:
            return

        try:
            # Reset state for this check run.
            self.listed_ips = {}
            self.report_file_handler = None
            self.csv_writer = None

            # Log start of check run.
            self.logger.log_info(
                f"Checking {len(ips)} IP addresses against {len(rbl_servers)} RBL and {len(dbl_servers)} DBL servers."
            )
            normalized_rbl_servers = self._normalized_server_list(rbl_servers)
            normalized_dbl_servers = self._normalized_server_list(dbl_servers)
            normalized_ips = self._normalized_ip_list(ips)

            thread_count = config.get_thread_count()
            if config.is_threading_enabled():
                self.logger.log_info(f"Using {thread_count} threads.")
                self._run_threaded_checks(
                    normalized_rbl_servers,
                    normalized_dbl_servers,
                    normalized_ips,
                    thread_count,
                )
            else:
                self.logger.log_info("Threading disabled; using sequential checks.")
                self._run_serial_checks(normalized_rbl_servers, normalized_dbl_servers, normalized_ips)

            # Close report file if it was opened.
            if self.report_file_handler:
                self.report_file_handler.close()

            # Log summary of check run.
            self.logger.log_info(f"Found {len(self.listed_ips)} listed IP addresses.")

            # Send notifications if IPs were found.
            if self.listed_ips:
                self.logger.log_debug(f"Listed IPs detected: {list(self.listed_ips.keys())}")

                # Filter out suppressed IPs from notifications.
                suppressed = config.get_active_suppressions()
                notification_ips = {ip: servers for ip, servers in self.listed_ips.items() if ip not in suppressed}
                for ip in self.listed_ips:
                    if ip in suppressed:
                        self.logger.log_info(f"SUPPRESSED: {ip} is listed but notifications are suppressed")

                if notification_ips:
                    # Send email notification if email is enabled.
                    if config.is_email_enabled():
                        self.logger.log_debug("Email notifications enabled, proceeding with email alerts")
                        self._send_email_report(notification_ips)
                    else:
                        self.logger.log_debug("Email notifications disabled in configuration")

                    # Send webhook notification if webhooks are enabled (independent of email).
                    if config.is_webhooks_enabled():
                        self.logger.log_debug("Webhooks are enabled, proceeding with webhook notification")
                        self._send_webhook_notification(notification_ips)
                    else:
                        self.logger.log_debug("Webhooks are disabled in configuration")
                else:
                    self.logger.log_debug("All listed IPs are suppressed, skipping notifications")

                # Cleanup old reports after notifications
                self._cleanup_old_reports()
            else:
                self.logger.log_debug("No listed IPs found, skipping email and webhook notifications")

        except Exception:
            # Capture exception information for logging.
            exc_type, exc_value, exc_traceback = sys.exc_info()
            # Format exception details.
            error_details = SignalHandler.format_exception(exc_type, exc_value, exc_traceback)
            # Log formatted exception if available.
            if error_details:
                # Create error-level logger to capture detailed exception.
                log_config = LogConfig(log_file=config.log_file, level=LogLevel.ERROR)
                logger = Logger(log_config)
                logger.log_error(error_details)

    def _send_email_report(self, ips: dict = None):
        """
        Send an email report of the listed IP addresses.
        Sends individual emails to each configured recipient.

        Args:
            ips: Dictionary of IPs to include in the report. Defaults to self.listed_ips.
        """
        if ips is None:
            ips = self.listed_ips
        self.logger.log_debug(f"Preparing to send email report for {len(ips)} listed IP(s)")

        # Build email message with header.
        mail_text = "The following IP addresses or derived domains were found on one or more DNS block lists:\n\n"
        # Add each listed IP with servers it appears on.
        for ip, servers in ips.items():
            mail_text += f"{ip} ===> {', '.join(servers)}\n"

        # Send email to each configured recipient.
        recipients = config.get_email_recipients()
        self.logger.log_debug(f"Sending emails to {len(recipients)} recipient(s)")

        for recipient in recipients:
            self.logger.log_debug(f"Sending email to: {recipient}")
            # Attempt to send email to this recipient.
            success, error = self.mail_client.send_plain(
                to_email=recipient,
                from_email=config.get_email_sender(),
                subject="DNS Block List Alert",
                message=mail_text
            )
            # Log any email sending errors.
            if not success:
                self.logger.log_error(f"Email send failed for {recipient}: {error}")
            else:
                self.logger.log_info(f"Email report sent successfully to {recipient}")

    def _send_webhook_notification(self, ips: dict = None):
        """
        Send webhook notification for listed IP addresses.
        Posts JSON data to all configured webhook URLs.

        Args:
            ips: Dictionary of IPs to include in the notification. Defaults to self.listed_ips.
        """
        # Check if webhook client is available.
        if not self.webhook_client:
            self.logger.log_warning("Webhook client not available, skipping webhook notification")
            return

        if ips is None:
            ips = self.listed_ips

        self.logger.log_debug(f"_send_webhook_notification called for {len(ips)} listed IP(s)")

        # Prepare structured data for webhook payload.
        webhook_data = {
            "ips": ips,
            "count": len(ips)
        }
        # Send notification and log result
        success, errors = self.webhook_client.send_notification(webhook_data)
        if success:
            self.logger.log_info(f"Webhook notification sent successfully for {len(self.listed_ips)} listed IP(s)")
        else:
            self.logger.log_warning(f"Webhook notification failed with errors: {errors}")

    @staticmethod
    def _report_check_type(check_type: str, target_source: str = '') -> str:
        """Return the user-facing report section label."""
        normalized = (check_type or '').strip().upper()
        source = (target_source or '').strip().lower()
        if normalized in ('RBL', 'IP'):
            return 'IP'
        if normalized in ('PTR', 'APEX'):
            return normalized
        if normalized == 'DBL':
            return 'PTR' if source == 'ptr' else 'APEX' if source == 'apex' else 'DBL'
        return normalized

    def _cleanup_old_reports(self):
        """
        Keeps only the last N report files in the report directory, deleting older ones.
        """
        report_dir = config.report_dir
        keep_n = config.get_keep_last_reports()
        if not report_dir or not keep_n:
            return
        report_dir = report_dir
        if not report_dir.exists():
            return
        # List all report_*.csv files, sort by mtime descending
        report_files = sorted(report_dir.glob('report_*.csv'), key=lambda f: f.stat().st_mtime, reverse=True)
        # Delete files beyond the N most recent
        for old_file in report_files[keep_n:]:
            try:
                old_file.unlink()
                self.logger.log_info(f"Deleted old report file: {old_file}")
            except Exception as e:
                self.logger.log_error(f"Failed to delete old report file {old_file}: {e}")
