import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from config import config
from logger import Logger, LogConfig, LogLevel
from mail import MailClient
from rblcheck import RBLCheck
from signals import SignalHandler


class DNSCheck:
    """
    Handles DNSBL checking with support for multithreading.
    Manages check coordination, result reporting, and email notifications.
    """

    def __init__(self, mail_client: MailClient, dnsrbl_checker: RBLCheck, logger: Logger):
        """
        Initialize the DNSBL Check Handler.

        Args:
            mail_client: MailClient instance for sending alerts.
            dnsrbl_checker: DNSRBLChecker instance for checking IPs.
            logger: Logger instance for logging.
        """
        # Mail client for sending email alerts on blacklisted IPs.
        self.mail_client = mail_client
        # DNSRBL checker instance for performing blacklist queries.
        self.dnsrbl_checker = dnsrbl_checker
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
        Check a single IP against a single DNSBL server.
        This method is executed by worker threads in the thread pool.

        Args:
            ip: The IP address to check.
            server: The DNSBL server to check against.

        Returns:
            tuple: (ip, server, is_listed, result_details) or None if shutdown requested.
        """
        # Return early if shutdown has been requested.
        if SignalHandler().is_shutdown_requested:
            return None

        try:
            # Query DNSRBL server for the IP address.
            is_listed = self.dnsrbl_checker.check(ip, server)
            # Extract result details from response (if listed).
            return (ip, server, is_listed, is_listed[1] if is_listed else None)
        except Exception as e:
            # Log error but don't fail the entire check run.
            self.logger.log_error(f"Error checking {ip} against {server}: {str(e)}")
            return None

    def _write_report(self, ip: str, server: str, result_details: str):
        """
        Write a report entry to the CSV file (thread-safe).
        Lazily initializes the report file on first write.

        Args:
            ip: The IP address.
            server: The DNSBL server.
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
                # Open report file for writing.
                self.report_file_handler = open(report_file_path, 'w', newline='')
                # Create CSV writer instance.
                self.csv_writer = csv.writer(self.report_file_handler)

            # Format current timestamp for report entry.
            timestamp = time.strftime("%d %b %Y %H:%M:%S", time.gmtime())
            # Write row to CSV report.
            self.csv_writer.writerow([timestamp, ip, server, result_details])
            # Flush to ensure data is written immediately.
            self.report_file_handler.flush()

    def _record_listed_ip(self, ip: str, server: str):
        """
        Record a listed IP (thread-safe).
        Maintains a dictionary of listed IPs and their corresponding servers.

        Args:
            ip: The IP address.
            server: The DNSBL server.
        """
        # Use lock to ensure thread-safe dictionary updates.
        with self.lock:
            # Create entry for IP if it doesn't exist.
            if ip not in self.listed_ips:
                self.listed_ips[ip] = []
            # Add server to IP's list if not already present.
            if server not in self.listed_ips[ip]:
                self.listed_ips[ip].append(server)

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

        # Unpack result tuple components.
        ip, server, is_listed, result_details = result

        # Handle positive listing result.
        if is_listed:
            # Write entry to CSV report file.
            self._write_report(ip, server, result_details)
            # Record this IP as listed on this server.
            self._record_listed_ip(ip, server)
            # Log the positive finding.
            self.logger.log_info(f"DIRTY: {ip} is listed on {server}")
        else:
            # Log the clean result at debug level.
            self.logger.log_debug(f"CLEAN: {ip} is not listed on {server}")

    def run(self, servers: list, ips: list):
        """
        Run the DNSBL check with multithreading support.
        Coordinates checking of all IPs against all servers.

        Args:
            servers: List of DNSBL servers (each server is a list/tuple).
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
            self.logger.log_info(f"Checking {len(ips)} IP addresses against {len(servers)} DNSBL servers.")
            self.logger.log_info(f"Using {config.get_thread_count()} threads.")

            # Prepare all check tasks as (ip, server) tuples.
            check_tasks = []
            for server in servers:
                # Exit early if shutdown requested during task preparation.
                if SignalHandler().is_shutdown_requested:
                    break
                for ip in ips:
                    # Exit early if shutdown requested during task preparation.
                    if SignalHandler().is_shutdown_requested:
                        break
                    # Extract first element from each (assuming CSV list format).
                    check_tasks.append((ip[0], server[0]))

            # Get configured thread count for the executor.
            thread_count = config.get_thread_count()
            # Create thread pool executor for concurrent checks.
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                # Submit all check tasks and collect futures.
                futures = {
                    executor.submit(self.check_ip_against_server, ip, server): (ip, server)
                    for ip, server in check_tasks
                }

                # Process results as they complete.
                for future in as_completed(futures):
                    # Exit early if shutdown requested during result processing.
                    if SignalHandler().is_shutdown_requested:
                        break

                    try:
                        # Get result from completed future.
                        result = future.result()
                        # Process the check result.
                        self._process_check_result(result)
                    except Exception as e:
                        # Log exceptions from individual check tasks.
                        ip, server = futures[future]
                        self.logger.log_error(f"Exception checking {ip} against {server}: {str(e)}")

                    # Small delay between processing results to avoid overwhelming the system.
                    time.sleep(0.01)

            # Close report file if it was opened.
            if self.report_file_handler:
                self.report_file_handler.close()

            # Log summary of check run.
            self.logger.log_info(f"Found {len(self.listed_ips)} listed IP addresses.")

            # Send email notification if IPs were found and email is enabled.
            if self.listed_ips and config.is_email_enabled():
                self._send_email_report()

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

    def _send_email_report(self):
        """
        Send an email report of the listed IP addresses.
        Sends individual emails to each configured recipient.
        """
        # Build email message with header.
        mail_text = "The following IP addresses were found on one or more DNS blacklists:\n\n"
        # Add each listed IP with servers it appears on.
        for ip, servers in self.listed_ips.items():
            mail_text += f"{ip} ===> {', '.join(servers)}\n"

        # Send email to each configured recipient.
        for recipient in config.get_email_recipients():
            # Attempt to send email to this recipient.
            success, error = self.mail_client.send_plain(
                to_email=recipient,
                from_email=config.get_email_sender(),
                subject="DNS Block List Alert",
                message=mail_text
            )
            # Log any email sending errors.
            if not success:
                self.logger.log_error(f"Mailer error: {error}")

