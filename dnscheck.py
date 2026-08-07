import csv
import ipaddress
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    Handles DNS RBL checking with support for multithreading.
    Manages check coordination, result reporting, and email notifications.
    """

    def __init__(self, mail_client: MailClient, dnsrbl_checker: RBLCheck, logger: Logger, webhook_client: WebhookClient = None):
        """
        Initialize the DNS RBL Check Handler.

        Args:
            mail_client: MailClient instance for sending alerts.
            dnsrbl_checker: DNS RBL Checker instance for checking IPs.
            logger: Logger instance for logging.
            webhook_client: WebhookClient instance for sending webhook notifications (optional).
        """
        # Mail client for sending email alerts on listed IPs.
        self.mail_client = mail_client
        # Webhook client for posting notifications to external services.
        self.webhook_client = webhook_client
        # DNS RBL Checker instance for performing RBL queries.
        self.dnsrbl_checker = dnsrbl_checker
        # Domain resolver for PTR/apex target derivation used by DBL checks.
        self.domain_resolver = DomainResolver(
            nameservers=config.get_nameservers(),
            nameservers_confirm=config.get_nameservers_confirm(),
        )
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
        # Path to the CSV report written in the current run (None if no IPs listed yet).
        self.current_report_path = None

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
            ip: The IP address.
            server: The DNS RBL server.
            result_details: Details about the listing.
        """
        # Use lock to ensure thread-safe file operations.
        with self.lock:
            # Create report file on first write (lazy initialization).
            if self.report_file_handler is None:
                # Generate timestamp-based filename for report.
                timestamp_filename = time.strftime("%Y%m%d%H%M%S", time.gmtime())
                # Construct full path to report file.
                report_file_path = config.report_dir / f"report_{timestamp_filename}.csv"
                # Store path so we can sort and reference it after the run.
                self.current_report_path = report_file_path
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
            obm_server = self._get_address_group(ip)
            self.csv_writer.writerow([
                timestamp,
                ip,
                check_type,
                target,
                target_source,
                server,
                obm_server,
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
            server: The DNS RBL server.
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
        Process the result of an IP check.
        Updates reports and alerts based on check outcome.

        Args:
            result: Tuple containing (ip, server, is_listed, result_details).
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

        matches = []
        for label, entries in config.get_address_groups().items():
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

    def run(self, rbl_servers: list, dbl_servers: list = None, ips: list = None):
        """
        Run DNS RBL/DBL checks with multithreading support.
        Supports both old signature run(servers, ips) and new run(rbl_servers, dbl_servers, ips).

        Args:
            rbl_servers: List of DNS RBL servers (each server is a list/tuple).
            dbl_servers: List of DNS DBL servers (each server is a list/tuple).
            ips: List of IPs to check (each IP is a list/tuple).
        """
        # Return early if shutdown has been requested.
        if SignalHandler().is_shutdown_requested:
            return

        # Backward compatibility: run(servers, ips)
        if ips is None:
            ips = dbl_servers if dbl_servers is not None else []
            dbl_servers = []

        if dbl_servers is None:
            dbl_servers = []

        try:
            # Reset state for this check run.
            self.listed_ips = {}
            self.report_file_handler = None
            self.csv_writer = None
            self.current_report_path = None

            # Log start of check run.
            self.logger.log_info(
                f"Checking {len(ips)} IP addresses against {len(rbl_servers)} RBL and {len(dbl_servers)} DBL servers."
            )
            self.logger.log_info(f"Using {config.get_thread_count()} threads.")

            def _normalized_server_list(raw_servers):
                normalized = []
                for row in raw_servers:
                    if not row:
                        continue
                    server = row[0].strip()
                    if not server:
                        continue
                    normalized.append(server)
                return normalized

            normalized_rbl_servers = _normalized_server_list(rbl_servers)
            normalized_dbl_servers = _normalized_server_list(dbl_servers)
            normalized_ips = [row[0].strip() for row in ips if row and row[0].strip()]

            # Get configured thread count for the executor.
            thread_count = config.get_thread_count()
            # Create thread pool executor for concurrent checks.
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = {}

                for server in normalized_rbl_servers:
                    if SignalHandler().is_shutdown_requested:
                        break
                    for ip in normalized_ips:
                        if SignalHandler().is_shutdown_requested:
                            break
                        fut = executor.submit(self.check_ip_against_server, ip, server)
                        futures[fut] = ('rbl', ip, server)

                # Build DBL task groups keyed by (domain, source, server). Multiple IPs
                # commonly share the same apex domain (e.g. all IPs in a /24 sending
                # pool with a shared registrable apex) — group them so we issue one
                # DNS query per unique target and fan the result back to every IP
                # that shares it. Prevents whole-pool cascades from a single
                # upstream DNS blip and cuts DBL query volume dramatically.
                dbl_task_groups = {}
                for ip in normalized_ips:
                    if SignalHandler().is_shutdown_requested:
                        break
                    domain_targets = self.domain_resolver.derive_check_targets(ip)
                    for domain, domain_source in sorted(domain_targets):
                        for server in normalized_dbl_servers:
                            key = (domain, domain_source, server)
                            dbl_task_groups.setdefault(key, []).append(ip)

                for (domain, domain_source, server), ips_sharing in dbl_task_groups.items():
                    if SignalHandler().is_shutdown_requested:
                        break
                    representative_ip = ips_sharing[0]
                    fut = executor.submit(
                        self.check_domain_against_server,
                        representative_ip,
                        domain,
                        domain_source,
                        server,
                    )
                    futures[fut] = ('dbl', tuple(ips_sharing), domain, domain_source, server)

                if len(dbl_task_groups) and normalized_dbl_servers:
                    self.logger.log_debug(
                        f"DBL apex dedup: {len(dbl_task_groups)} unique (target, server) "
                        f"pairs across {len(normalized_ips)} IPs × {len(normalized_dbl_servers)} DBL servers"
                    )

                # Process results as they complete.
                for future in as_completed(futures):
                    # Exit early if shutdown requested during result processing.
                    if SignalHandler().is_shutdown_requested:
                        break

                    meta = futures[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        if meta[0] == 'rbl':
                            _, ip, server = meta
                            self.logger.log_error(f"Exception checking {ip} against {server}: {str(e)}")
                        else:
                            _, ips_sharing, domain, domain_source, server = meta
                            self.logger.log_error(
                                f"Exception checking {len(ips_sharing)} IPs domain target "
                                f"{domain} ({domain_source}) against {server}: {str(e)}"
                            )
                        time.sleep(0.01)
                        continue

                    if result is None:
                        time.sleep(0.01)
                        continue

                    if meta[0] == 'rbl':
                        self._process_check_result(result)
                    else:
                        # Fan the single (target, server) result out to every IP that
                        # shares the target. Each IP produces its own CSV row and
                        # listed_ips entry so downstream reporting is unchanged.
                        _, ips_sharing, domain, domain_source, server = meta
                        (_rep_ip, r_target, r_target_source, r_server,
                         is_listed, response_code, txt_context) = result
                        for ip in ips_sharing:
                            fanned = (
                                ip, r_target, r_target_source, r_server,
                                is_listed, response_code, txt_context,
                            )
                            self._process_check_result(fanned)

                    # Small delay between processing results to avoid overwhelming the system.
                    time.sleep(0.01)

            # Close report file if it was opened, then sort it by IP for consistent output.
            if self.report_file_handler:
                self.report_file_handler.close()
                if self.current_report_path:
                    self._sort_report_file(self.current_report_path)

            # Log summary of check run.
            self.logger.log_info(f"Found {len(self.listed_ips)} listed IP addresses.")

            # Load previous run's CSV for delta comparison (existing local logs seed history).
            previous_results = self._load_previous_results(self.current_report_path)

            # DBL persistence gate: a DBL sighting must appear in two consecutive
            # runs (or the previous CSV) before it becomes alertable. Suppresses
            # transient upstream DNS anomalies where a single bad response for a
            # shared apex flips an entire /24 pool for one run. See
            # docs/incidents/obm-oxygen-dbl-false-positive-2026-08-07.md.
            previous_pairs = self._flatten_previous_pairs(previous_results)
            pending_pairs = self._load_pending_pairs()
            alertable_listed_ips, new_pending_pairs = self._apply_persistence_gate(
                self.listed_ips, previous_pairs, pending_pairs
            )
            self._save_pending_pairs(new_pending_pairs)

            # Pool-flood detection: log a WARNING if a large share of a pool is
            # about to alert on a single DBL server via a single apex. Alerts
            # still fire (real listings can be pool-wide) but the log flags the
            # pattern operators should double-check before rotating IPs.
            self._log_pool_flood_warnings(alertable_listed_ips)

            newly_listed, still_listed, delisted = self._categorize_results(
                alertable_listed_ips, previous_results
            )
            self.logger.log_debug(
                f"Delta: {len(newly_listed)} newly listed, "
                f"{len(still_listed)} still listed, "
                f"{len(delisted)} delisted"
            )

            # Filter suppressions from actively-listed categories (not from delisted).
            suppressed = config.get_active_suppressions()

            def _filter_suppressed(d):
                out = {}
                for ip, s in d.items():
                    if ip in suppressed:
                        self.logger.log_info(f"SUPPRESSED: {ip} is listed but notifications are suppressed")
                    else:
                        out[ip] = s
                return out

            notif_newly    = _filter_suppressed(newly_listed)
            notif_still    = _filter_suppressed(still_listed)
            notif_delisted = {ip: s for ip, s in delisted.items() if ip not in suppressed}

            should_notify = bool(notif_newly or notif_still or notif_delisted)

            if should_notify:
                from pools import PoolResolver
                pool_resolver = PoolResolver(config.get_pools_file(), logger=self.logger)

                if config.is_email_enabled():
                    self.logger.log_debug("Email notifications enabled, proceeding with email alerts")
                    email_ips = {**notif_newly, **notif_still}
                    if email_ips:
                        self._send_email_report(email_ips)
                else:
                    self.logger.log_debug("Email notifications disabled in configuration")

                if config.is_webhooks_enabled():
                    self.logger.log_debug("Webhooks are enabled, proceeding with categorized notifications")
                    self._send_categorized_notifications(
                        newly=notif_newly,
                        still=notif_still,
                        delisted=notif_delisted,
                        pool_resolver=pool_resolver,
                        report_path=self.current_report_path,
                    )
                else:
                    self.logger.log_debug("Webhooks are disabled in configuration")
            else:
                self.logger.log_debug("No changes detected, skipping notifications")

            # Cleanup old reports after notifications.
            self._cleanup_old_reports()

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
        mail_text = "The following IP addresses were found on one or more DNS RBLs:\n\n"
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
                subject="DNS RBL Alert",
                message=mail_text
            )
            # Log any email sending errors.
            if not success:
                self.logger.log_error(f"Email send failed for {recipient}: {error}")
            else:
                self.logger.log_info(f"Email report sent successfully to {recipient}")


    @staticmethod
    def _sort_ips(ip_dict: dict) -> list:
        """Return ip_dict items sorted numerically by IP address."""
        import ipaddress as _ip

        def _key(item):
            try:
                return _ip.ip_address(item[0])
            except ValueError:
                return _ip.ip_address('0.0.0.0')

        return sorted(ip_dict.items(), key=_key)

    def _sort_report_file(self, report_path):
        """Sort report sections and add blank separators between check types."""
        import ipaddress as _ip
        import csv as _csv
        from pathlib import Path as _Path
        p = _Path(report_path)
        if not p.exists():
            return
        try:
            with open(p, newline='') as f:
                rows = list(_csv.reader(f))

            if not rows:
                return

            has_header = rows[0] and rows[0][0] == "timestamp"
            header = rows[0] if has_header else None
            data_rows = rows[1:] if has_header else rows

            check_type_order = {'IP': 0, 'PTR': 1, 'APEX': 2}

            def _key(row):
                try:
                    source_ip = _ip.ip_address(row[1].strip())
                except (ValueError, IndexError):
                    source_ip = _ip.ip_address('0.0.0.0')
                check_type = self._report_check_type(
                    row[2].strip() if len(row) > 2 else '',
                    row[4].strip() if len(row) > 4 else '',
                )
                target = row[3].strip() if len(row) > 3 else ''
                server = row[5].strip() if len(row) > 5 else (row[2].strip() if len(row) > 2 else '')
                return (check_type_order.get(check_type, 99), source_ip, target, server)

            for row in data_rows:
                if len(row) > 2:
                    row[2] = self._report_check_type(
                        row[2].strip(),
                        row[4].strip() if len(row) > 4 else '',
                    )
            data_rows.sort(key=_key)
            spaced_rows = []
            previous_type = None
            for row in data_rows:
                current_type = row[2] if len(row) > 2 else ''
                if spaced_rows and current_type != previous_type:
                    spaced_rows.append([])
                spaced_rows.append(row)
                previous_type = current_type

            with open(p, 'w', newline='') as f:
                writer = _csv.writer(f)
                if header:
                    writer.writerow(header)
                writer.writerows(spaced_rows)
        except Exception as e:
            self.logger.log_error(f"_sort_report_file failed: {e}")

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

    def _load_previous_results(self, current_report_path=None) -> dict:
        """Load the most recent previous CSV report into a {ip: set(servers)} dict.

        Excludes current_report_path so we always read the prior run, not this one.
        Existing local log files seed history immediately on first deployment.
        """
        from pathlib import Path as _Path
        import csv as _csv
        try:
            report_dir = _Path(config.report_dir)
            files = sorted(
                report_dir.glob('report_*.csv'),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            if current_report_path:
                files = [f for f in files if f != _Path(current_report_path)]
            if not files:
                self.logger.log_debug("_load_previous_results: no previous report found")
                return {}
            results = {}
            with open(files[0], newline='') as f:
                for row in _csv.reader(f):
                    if not row:
                        continue
                    if row[0] == "timestamp":
                        continue
                    if len(row) >= 6:
                        ip, server = row[1].strip(), row[5].strip()
                    elif len(row) >= 3:
                        ip, server = row[1].strip(), row[2].strip()
                    else:
                        continue
                    if ip and server:
                        results.setdefault(ip, set()).add(server)
            self.logger.log_debug(
                f"_load_previous_results: {len(results)} IPs from {files[0].name}"
            )
            return results
        except Exception as e:
            self.logger.log_error(f"_load_previous_results failed: {e}")
            return {}

    def _categorize_results(self, current: dict, previous: dict):
        """Categorize current results against previous run.

        Returns (newly_listed, still_listed, delisted) — each a {ip: servers} dict.
        """
        newly    = {ip: s for ip, s in current.items() if ip not in previous}
        still    = {ip: s for ip, s in current.items() if ip in previous}
        delisted = {ip: sorted(s) for ip, s in previous.items() if ip not in current}
        return newly, still, delisted

    # ------------------------------------------------------------------
    # DBL persistence gate (see docs/incidents/obm-oxygen-dbl-false-positive-2026-08-07.md)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_dbl_label(server_label: str) -> bool:
        """Server labels formatted as 'server [source:target]' are DBL sightings."""
        return isinstance(server_label, str) and ' [' in server_label and server_label.endswith(']')

    @staticmethod
    def _dbl_server_from_label(server_label: str) -> str:
        """Return the DBL server hostname from a 'server [source:target]' label."""
        return server_label.split(' ', 1)[0]

    def _pending_file_path(self):
        from pathlib import Path as _Path
        return _Path(config.report_dir) / 'dbl_pending.json'

    def _load_pending_pairs(self) -> set:
        """Load previously-recorded first-sighting DBL (ip, server) pairs."""
        import json as _json
        path = self._pending_file_path()
        try:
            if not path.exists():
                return set()
            with open(path) as f:
                data = _json.load(f)
            pairs = data.get('pairs', []) if isinstance(data, dict) else []
            out = set()
            for entry in pairs:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    ip, server = str(entry[0]), str(entry[1])
                    if ip and server:
                        out.add((ip, server))
            self.logger.log_debug(f"_load_pending_pairs: {len(out)} pending DBL sightings from {path.name}")
            return out
        except Exception as e:
            self.logger.log_error(f"_load_pending_pairs failed: {e}")
            return set()

    def _save_pending_pairs(self, pairs: set):
        """Persist current run's first-sighting DBL (ip, server) pairs."""
        import json as _json
        path = self._pending_file_path()
        try:
            payload = {'pairs': sorted([list(p) for p in pairs])}
            with open(path, 'w') as f:
                _json.dump(payload, f, indent=2)
            self.logger.log_debug(f"_save_pending_pairs: wrote {len(pairs)} pending sightings to {path.name}")
        except Exception as e:
            self.logger.log_error(f"_save_pending_pairs failed: {e}")

    @staticmethod
    def _flatten_previous_pairs(previous_results: dict) -> set:
        """Convert {ip: set(servers)} into a set of (ip, server) tuples."""
        pairs = set()
        for ip, servers in previous_results.items():
            if isinstance(servers, (list, set, tuple)):
                for s in servers:
                    pairs.add((ip, s))
            elif isinstance(servers, str):
                pairs.add((ip, servers))
        return pairs

    def _apply_persistence_gate(self, listed_ips: dict, previous_pairs: set, pending_pairs: set):
        """Filter DBL sightings that have not yet appeared in two consecutive runs.

        RBL (IP-based) sightings pass through unchanged — they don't cascade via
        shared identifiers.

        A DBL sighting is alertable when its (ip, dbl_server) pair either:
          * appeared in the previous run's CSV, or
          * appeared in the pending file (previous run's first sightings).

        First-time DBL sightings are recorded in the returned `new_pending`
        set and stripped from the alertable dict. CSV rows are unaffected —
        the full audit trail is preserved.

        Returns:
            (alertable_listed_ips, new_pending_pairs)
        """
        require_runs = config.get_require_consecutive_runs()
        if require_runs <= 1:
            return dict(listed_ips), set()

        alertable = {}
        new_pending = set()
        held_count = 0
        for ip, labels in listed_ips.items():
            if not isinstance(labels, (list, tuple, set)):
                alertable[ip] = labels
                continue
            kept = []
            for label in labels:
                if not self._is_dbl_label(label):
                    kept.append(label)
                    continue
                dbl_server = self._dbl_server_from_label(label)
                key = (ip, dbl_server)
                if key in previous_pairs or key in pending_pairs:
                    kept.append(label)
                else:
                    new_pending.add(key)
                    held_count += 1
                    self.logger.log_info(
                        f"PENDING: {ip} DBL sighting via {label} — first sighting, holding for next run"
                    )
            if kept:
                alertable[ip] = kept

        if held_count:
            self.logger.log_info(
                f"Persistence gate: held {held_count} first-sighting DBL entries "
                f"(require_consecutive_runs={require_runs})"
            )
        return alertable, new_pending

    def _log_pool_flood_warnings(self, alertable_listed_ips: dict):
        """Emit WARNING when a pool-wide DBL cascade is about to alert.

        Groups alertable DBL sightings by (pool_label, dbl_server, apex). If any
        group exceeds `pool_flood_threshold`, log a warning naming the shared
        apex — this is the fingerprint of a transient upstream DNS anomaly.
        Alerts still fire; the warning is guidance for the operator reading
        Slack.
        """
        threshold = config.get_pool_flood_threshold()
        if threshold <= 0 or not alertable_listed_ips:
            return

        from collections import defaultdict
        groups = defaultdict(list)  # (pool, dbl_server, apex) -> [ip, ...]
        for ip, labels in alertable_listed_ips.items():
            if not isinstance(labels, (list, tuple, set)):
                continue
            pool = self._get_address_group(ip) or '(unlabeled)'
            for label in labels:
                if not self._is_dbl_label(label):
                    continue
                dbl_server = self._dbl_server_from_label(label)
                meta = label.rsplit(' [', 1)[1][:-1]  # 'source:target'
                if ':' not in meta:
                    continue
                source, target = meta.split(':', 1)
                if source != 'apex':
                    continue
                groups[(pool, dbl_server, target)].append(ip)

        for (pool, dbl_server, apex), ips in groups.items():
            if len(ips) >= threshold:
                self.logger.log_warning(
                    f"POOL_FLOOD: {len(ips)} IPs of pool '{pool}' listed on {dbl_server} "
                    f"via shared apex '{apex}' — consistent with a transient DNS anomaly. "
                    f"Verify against a second resolver before rotating IPs."
                )

    def _send_categorized_notifications(self, newly, still, delisted, pool_resolver=None, report_path=None):
        """Send one Slack summary message, then upload the CSV as a file."""
        if not self.webhook_client:
            self.logger.log_warning("Webhook client not available, skipping notifications")
            return

        def _classify_entries(entries: dict):
            ip_items = set()
            domain_items = set()
            for ip, server_labels in entries.items():
                labels = server_labels if isinstance(server_labels, (list, set, tuple)) else [server_labels]
                has_rbl = False
                for label in labels:
                    if not isinstance(label, str):
                        continue
                    if " [" in label and label.endswith("]"):
                        meta = label.rsplit(" [", 1)[1][:-1]  # ptr:example.com / apex:example.com
                        if ":" in meta:
                            _, domain = meta.split(":", 1)
                            if domain:
                                domain_items.add(domain)
                    else:
                        has_rbl = True
                if has_rbl:
                    ip_items.add(ip)
            return sorted(ip_items), sorted(domain_items)

        current_active = {}
        current_active.update(still)
        current_active.update(newly)

        total_ips, total_domains = _classify_entries(current_active)
        new_ips, new_domains = _classify_entries(newly)
        delisted_ips, delisted_domains = _classify_entries(delisted)
        affected_servers = {}
        for ip in current_active:
            label = self._get_address_group(ip)
            if label:
                affected_servers[label] = affected_servers.get(label, 0) + 1
        ordered_affected_servers = [
            {"server": label, "listed_ips": count}
            for label, count in sorted(
                affected_servers.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

        summary_data = {
            "summary": {
                "total_listed_ips": len(total_ips),
                "total_listed_domains": len(total_domains),
                "newly_listed_ips": new_ips,
                "newly_listed_domains": new_domains,
                "delisted_ips": delisted_ips,
                "delisted_domains": delisted_domains,
                "affected_servers": ordered_affected_servers,
            }
        }

        ok, errors = self.webhook_client.send_notification(summary_data, pool_resolver=pool_resolver)
        if ok:
            self.logger.log_info(
                f"Slack summary sent (ips={len(total_ips)}, domains={len(total_domains)}, "
                f"new_ips={len(new_ips)}, new_domains={len(new_domains)}, "
                f"delisted_ips={len(delisted_ips)}, delisted_domains={len(delisted_domains)})"
            )
        else:
            self.logger.log_warning(f"Slack summary notification failed: {errors}")

        # Upload the full sorted CSV as a Slack file (best-effort, non-fatal).
        if report_path:
            ok, err = self.webhook_client.upload_csv_to_slack(report_path)
            if not ok:
                self.logger.log_warning(f"CSV Slack upload failed (non-fatal): {err}")

    def _cleanup_old_reports(self):
        """
        Keeps only the last N report files in the report directory, deleting older ones.
        """
        from pathlib import Path
        report_dir = config.report_dir
        keep_n = config.get_keep_last_reports()
        if not report_dir or not keep_n:
            return
        report_dir = Path(report_dir)
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
