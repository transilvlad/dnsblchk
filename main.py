import argparse
import sys
import time
from pathlib import Path

from api_client import ApiClient
from config import config
from dnscheck import DNSCheck
from files import FileHandler
from logger import Logger, LogConfig
from mail import MailClient
from rblcheck import RBLCheck
from signals import SignalHandler
from webhook import WebhookClient


class MainApplication:
    """
    Main application class for the DNS Block List Checker service.
    Orchestrates initialization, configuration loading, and the main check loop.
    """

    def __init__(self, app_config=None):
        """Initialize the application with all instance variables set to None."""
        if app_config is not None:
            config.load(app_config)
        # Logger instance for application-wide logging.
        self.logger = None
        # Signal handler for graceful shutdown coordination.
        self.signal_handler = None
        # Mail client for sending email alerts.
        self.mail_client = None
        # Webhook client for posting notifications to external services.
        self.webhook_client = None
        # API client for fetching IP addresses from an external API.
        self.api_client = None
        # DNS block list checker instance for querying RBLs and DBLs.
        self.dnsrbl_checker = None
        # Check handler that orchestrates DNS block list checks.
        self.check_handler = None
        # List of DNS RBL servers loaded from configuration.
        self.rbls = None
        # List of DNS DBL servers loaded from configuration.
        self.dbls = None
        # List of IP addresses loaded from configuration.
        self.ips = None

    def _setup_logger(self):
        """Set up the logger with config-driven settings."""
        # Create logger configuration from application config.
        run_log_dir = config.get_run_log_dir()
        log_config = LogConfig(
            log_file=config.log_file,
            log_dir=config.log_dir,
            level=config.get_log_level(),
            console_print=config.get_console_print(),
            run_log_dir=Path(run_log_dir) if run_log_dir else None,
            keep_last_runs=config.get_keep_last_runs()
        )
        # Clear log file if configured
        if config.get_clear_log_on_start() and config.log_file:
            try:
                with open(config.log_file, 'w') as f:
                    pass  # Truncate log file
            except Exception as e:
                print(f"Failed to clear log file on start: {e}")
        # Initialize logger instance with the configuration.
        self.logger = Logger(log_config)
        self.logger.log_debug(f"Logger configured: log_file={config.log_file}, log_dir={config.log_dir}, level={config.get_log_level()}")

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        # Create signal handler singleton instance.
        self.signal_handler = SignalHandler()
        # Register SIGINT and SIGTERM signal handlers.
        self.signal_handler.setup_signal_handlers()
        self.logger.log_debug("Signal handlers setup complete (SIGINT and SIGTERM)")

    def _setup_clients_and_checkers(self):
        """Initialize mail client and DNS block list checker."""
        self.logger.log_debug(f"Setting up mail client: smtp_host={config.get_smtp_host()}, smtp_port={config.get_smtp_port()}, use_tls={config.get_smtp_use_tls()}, use_ssl={config.get_smtp_use_ssl()}")
        # Create mail client for sending email notifications with auth and encryption settings.
        self.mail_client = MailClient(
            smtp_host=config.get_smtp_host(),
            smtp_port=config.get_smtp_port(),
            smtp_user=config.get_smtp_user() or None,
            smtp_password=config.get_smtp_password() or None,
            use_tls=config.get_smtp_use_tls(),
            use_ssl=config.get_smtp_use_ssl()
        )
        self.logger.log_debug("Mail client initialized successfully")

        self.logger.log_debug(f"Setting up webhook client: webhook_urls={config.get_webhook_urls()}, timeout={config.get_webhook_timeout()}")
        # Create webhook client with configured URLs, timeout, and Slack
        # bot credentials (used for CSV file uploads when configured).
        self.webhook_client = WebhookClient(
            webhook_urls=config.get_webhook_urls(),
            timeout=config.get_webhook_timeout(),
            slack_bot_token=config.get_slack_bot_token(),
            slack_channel_id=config.get_slack_channel_id(),
            logger=self.logger,
        )
        self.logger.log_debug("Webhook client initialized successfully")

        # Create API client if API update is enabled.
        if config.is_api_update_enabled():
            self.logger.log_debug(f"Setting up API client: url={config.get_api_update_url()}, auth_type={config.get_api_update_auth_type()}, timeout={config.get_api_update_timeout()}")
            self.api_client = ApiClient(
                url=config.get_api_update_url(),
                auth_type=config.get_api_update_auth_type(),
                username=config.get_api_update_username(),
                password=config.get_api_update_password(),
                bearer_token=config.get_api_update_bearer_token(),
                timeout=config.get_api_update_timeout(),
                logger=self.logger
            )
            self.logger.log_debug("API client initialized successfully")

        primary_ns = config.get_nameservers()
        confirm_ns = config.get_nameservers_confirm()
        self.logger.log_debug(
            f"Setting up DNS block list checker with nameservers={primary_ns}, "
            f"confirm={confirm_ns or 'disabled'}"
        )
        # Create DNS block list checker instance. Confirm nameservers, when
        # non-empty, re-check positive listings; the logger receives DISPUTED
        # and RBL_ERROR_CODE warnings when responses look suspicious.
        self.dnsrbl_checker = RBLCheck(
            nameservers=primary_ns,
            nameservers_confirm=confirm_ns,
            logger=self.logger,
        )
        self.logger.log_debug("DNS block list checker initialized successfully")

    def _load_configuration(self):
        """Load servers and IPs from configuration files."""
        # Load DNS RBL servers from CSV file.
        rbls_file = config.get_rbls_file()
        self.rbls = FileHandler.load_csv(rbls_file) if rbls_file and rbls_file.exists() else []
        # Load DNS DBL servers from CSV file.
        dbls_file = config.get_dbls_file()
        self.dbls = FileHandler.load_csv(dbls_file) if dbls_file and dbls_file.exists() else []
        # Load IP addresses to check from CSV file.
        self.ips = FileHandler.load_csv(config.ips_file)
        # Log summary of loaded configuration.
        self.logger.log_info(
            f"Loaded {len(self.rbls)} RBL servers, {len(self.dbls)} DBL servers, and {len(self.ips)} IP addresses."
        )

    def _initialize(self):
        """Initialize all application components in proper order."""
        # Set up logging first so subsequent initialization is logged.
        self._setup_logger()
        self.logger.log_info("DNSblChk service started.")

        # Set up signal handlers to allow graceful shutdown.
        self._setup_signal_handlers()
        # Initialize SMTP and DNS clients.
        self._setup_clients_and_checkers()
        # Load servers and IP addresses from configuration files.
        self._load_configuration()
        self.logger.log_debug("Initialization complete. All components are ready.")

        # Create check handler with initialized clients.
        self.check_handler = DNSCheck(self.mail_client, self.dnsrbl_checker, self.logger, self.webhook_client)

    def _update_ips_from_api(self):
        """
        Update IP addresses from the API if API update is enabled.
        If successful, updates self.ips with the fetched IPs.
        If failed, keeps the existing IPs from the config file.
        """
        if not config.is_api_update_enabled():
            self.logger.log_debug("API update is disabled, skipping IP update from API")
            return

        if not self.api_client:
            self.logger.log_warning("API update is enabled but API client was not initialized")
            return

        self.logger.log_info("Attempting to update IP addresses from API")
        success, ips, error = self.api_client.fetch_ips()

        if success and ips:
            # Convert IPs to the format expected by the checker (list of lists)
            self.ips = [[ip] for ip in ips]
            self.logger.log_info(f"Successfully updated {len(ips)} IP address(es) from API")
        else:
            self.logger.log_warning(f"Failed to update IPs from API: {error}. Using existing ips.txt configuration.")

    def _run_checks(self):
        """Run the DNS block list checks against all servers and IPs."""
        # Update IPs from API if enabled before running checks.
        self._update_ips_from_api()
        # Delegate to check handler to perform the actual checks.
        self.check_handler.run(self.rbls, self.dbls, self.ips)

    def _sleep_with_shutdown_check(self, duration: int):
        """
        Sleep for a specified duration while allowing graceful shutdown.
        Checks shutdown status every 10 seconds to enable quick response to signals.

        Args:
            duration: Sleep duration in seconds.
        """
        # Split sleep into 10-second intervals to check for shutdown signals.
        for _ in range(int(duration / 10)):
            # Exit early if shutdown signal has been received.
            if self.signal_handler.is_shutdown_requested:
                break
            # Sleep for 10 seconds before checking shutdown status again.
            time.sleep(10)

    def run(self):
        """Run the main application loop with proper initialization and cleanup."""
        # Initialize all components before entering the main loop.
        self._initialize()

        try:
            # Main event loop: continue running until shutdown is requested.
            while not self.signal_handler.is_shutdown_requested:
                try:
                    # Start new run log file
                    self.logger.start_run()

                    # Execute DNS block list checks for all configured servers and IPs.
                    self.logger.log_debug("Starting DNS RBL check run.")
                    self._run_checks()

                    # End run log file
                    self.logger.end_run()

                    # Check if run-once mode is enabled (useful for testing).
                    if config.run_once:
                        self.logger.log_debug("Run-once mode enabled. Exiting.")
                        break

                    # Calculate sleep duration from configuration (in hours).
                    sleep_duration = config.sleep_hours * 3600
                    self.logger.log_info(f"Sleeping for {config.sleep_hours} hours...")
                    # Sleep while checking for shutdown signals periodically.
                    self._sleep_with_shutdown_check(sleep_duration)

                except Exception as e:
                    # Ensure cleanup on error
                    self.logger.end_run()
                    self.logger.log_error(f"Check cycle failed: {e}")
                    if config.run_once:
                        break

        finally:
            # Ensure cleanup happens regardless of how the loop exits.
            self.logger.log_info("DNSblChk service shutdown complete.")


def _parse_args(argv=None):
    """Parse command-line arguments for direct and packaged execution."""
    parser = argparse.ArgumentParser(description="DNS Block List Checker")
    parser.add_argument("config_path", nargs="?", help="Path to a YAML configuration file")
    parser.add_argument("-c", "--config", dest="config_option", help="Path to a YAML configuration file")
    args = parser.parse_args(argv)

    if args.config_path and args.config_option and args.config_path != args.config_option:
        parser.error("provide only one config path")
    return args.config_option or args.config_path


def main(argv=None):
    """
    Main entry point for the DNS Block List Checker service.
    """
    cfg_path = _parse_args(argv)
    try:
        config.load(cfg_path)
    except Exception as e:
        target = cfg_path if cfg_path else "default configuration locations"
        print(f"Failed to load configuration from {target}: {e}", file=sys.stderr)
        raise

    app = MainApplication()
    app.run()


if __name__ == "__main__":
    main()
