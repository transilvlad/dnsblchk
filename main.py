import sys
import time

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
    Main application class for the DNSBL checker service.
    Orchestrates initialization, configuration loading, and the main check loop.
    """

    def __init__(self):
        """Initialize the application with all instance variables set to None."""
        # Logger instance for application-wide logging.
        self.logger = None
        # Signal handler for graceful shutdown coordination.
        self.signal_handler = None
        # Mail client for sending email alerts.
        self.mail_client = None
        # Webhook client for posting notifications to external services.
        self.webhook_client = None
        # DNSRBL checker instance for querying blacklists.
        self.dnsrbl_checker = None
        # Check handler that orchestrates DNSBL checks.
        self.check_handler = None
        # List of DNSBL servers loaded from configuration.
        self.servers = None
        # List of IP addresses loaded from configuration.
        self.ips = None

    def _setup_logger(self):
        """Set up the logger with config-driven settings."""
        # Create logger configuration from application config.
        log_config = LogConfig(
            log_file=config.log_file,
            log_dir=config.log_dir,
            level=config.get_log_level(),
            console_print=config.get_console_print()
        )
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
        """Initialize mail client and DNSRBL checker."""
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
        # Create webhook client with configured URLs and timeout.
        self.webhook_client = WebhookClient(
            webhook_urls=config.get_webhook_urls(),
            timeout=config.get_webhook_timeout(),
            logger=self.logger
        )
        self.logger.log_debug("Webhook client initialized successfully")

        self.logger.log_debug(f"Setting up DNSRBL checker with nameservers: {config.get_nameservers()}")
        # Create DNSRBL checker instance with nameservers from config.
        self.dnsrbl_checker = RBLCheck(config.get_nameservers())
        self.logger.log_debug("DNSRBL checker initialized successfully")

    def _load_configuration(self):
        """Load servers and IPs from configuration files."""
        # Load DNSBL servers from CSV file.
        self.servers = FileHandler.load_csv(config.servers_file)
        # Load IP addresses to check from CSV file.
        self.ips = FileHandler.load_csv(config.ips_file)
        # Log summary of loaded configuration.
        self.logger.log_info(f"Loaded {len(self.servers)} DNSBL servers and {len(self.ips)} IP addresses.")

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

        # Create check handler with initialized clients.
        self.check_handler = DNSCheck(self.mail_client, self.dnsrbl_checker, self.logger, self.webhook_client)

    def _run_checks(self):
        """Run the DNSBL checks against all servers and IPs."""
        # Delegate to check handler to perform the actual checks.
        self.check_handler.run(self.servers, self.ips)

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
                # Execute DNSBL checks for all configured servers and IPs.
                self._run_checks()

                # Check if run-once mode is enabled (useful for testing).
                if config.run_once:
                    self.logger.log_debug("Run-once mode enabled. Exiting.")
                    break

                # Calculate sleep duration from configuration (in hours).
                sleep_duration = config.sleep_hours * 3600
                self.logger.log_info(f"Sleeping for {config.sleep_hours} hours...")
                # Sleep while checking for shutdown signals periodically.
                self._sleep_with_shutdown_check(sleep_duration)

        finally:
            # Ensure cleanup happens regardless of how the loop exits.
            self.logger.log_info("DNSblChk service shutdown complete.")


def main():
    """
    Main entry point for the DNSBL checker service.
    """
    # If a config path is provided as the first CLI argument, load it.
    # Example: python3 main.py config/config-local.yaml
    if len(sys.argv) > 1:
        cfg_path = sys.argv[1]
        try:
            config.load(cfg_path)
        except Exception as e:
            print(f"Failed to load custom configuration from {cfg_path}: {e}")
            raise

    app = MainApplication()
    app.run()


if __name__ == "__main__":
    main()
