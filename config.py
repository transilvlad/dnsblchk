from pathlib import Path

import yaml

from logger import LogLevel


class Config:
    """
    Handles loading the configuration from config.yaml and provides access to the settings.
    Supports nested configuration sections for logging, email, and threading.
    """

    def __init__(self, config_path: str | None = None):
        """Loads the configuration from a YAML file and resolves file paths.

        Args:
            config_path: Optional path to a YAML config file. If None, defaults to
                         the repository `config/config.yaml` next to this module.
        """
        # store application root path for later path resolution
        self._root_path = Path(__file__).parent
        # internal storage for config data
        self._config_data = {}

        # Load the provided config or default
        self.load(config_path)

    def load(self, config_path: str | Path | None = None):
        """
        Load or reload configuration from the given path.

        If config_path is None, loads from the repository default: `config/config.yaml`.
        Relative paths are resolved relative to the project root (module directory).
        """
        # Determine which path to use
        if config_path is None:
            path = self._root_path / 'config/config.yaml'
        else:
            p = Path(config_path)
            # If a relative path was provided, interpret it relative to project root
            path = p if p.is_absolute() else (self._root_path / p)

        # Read YAML
        with open(path, 'r') as f:
            self._config_data = yaml.safe_load(f) or {}

        # Resolve relative paths in the new config
        self._resolve_paths()

    def _resolve_paths(self):
        """Resolves all file paths in the config to be absolute."""
        # Resolve servers file path to absolute if present.
        if 'servers_file' in self._config_data:
            self._config_data['servers_file'] = self._get_absolute_path('servers_file')
        # Resolve IPs file path to absolute if present.
        if 'ips_file' in self._config_data:
            self._config_data['ips_file'] = self._get_absolute_path('ips_file')
        # Resolve report directory path to absolute if present.
        if 'report_dir' in self._config_data:
            self._config_data['report_dir'] = self._get_absolute_path('report_dir')

        # Resolve logging paths from nested logging config section.
        logging_config = self._config_data.get('logging', {})
        if 'log_dir' in logging_config:
            # Resolve log directory to absolute path.
            logging_config['log_dir'] = self._get_absolute_path_from_logging('log_dir')
        if 'log_file' in logging_config:
            # Combine log_dir and log_file to create the full path.
            log_dir = logging_config.get('log_dir')
            log_filename = logging_config.get('log_file')
            if log_dir and log_filename:
                # Create absolute path by combining log_dir with log_file.
                abs_log_dir = Path(log_dir) if isinstance(log_dir, Path) else (self._root_path / log_dir)
                # Store the combined absolute path.
                logging_config['log_file'] = abs_log_dir / log_filename
            else:
                # Fallback to old behavior if either is missing.
                logging_config['log_file'] = self._get_absolute_path_from_logging('log_file')

    def _get_absolute_path(self, key: str) -> Path:
        """Returns an absolute path for a given config key."""
        # Combine with relative path from config.
        rel = self._config_data.get(key, '')
        return Path(rel) if Path(rel).is_absolute() else (self._root_path / rel)

    def _get_absolute_path_from_logging(self, key: str) -> Path:
        """Returns an absolute path for a given key in the logging config."""
        # Get logging configuration section.
        logging_config = self._config_data.get('logging', {})
        # Combine root with relative path from logging config.
        rel = logging_config.get(key, '')
        return Path(rel) if Path(rel).is_absolute() else (self._root_path / rel)

    def __getattr__(self, name):
        """Provides attribute-style access to the configuration settings."""
        # Check top-level configuration keys first.
        if name in self._config_data:
            return self._config_data[name]

        # Check if the attribute is in the nested logging config.
        logging_config = self._config_data.get('logging', {})
        if name in logging_config:
            return logging_config[name]

        # Check if the attribute is in the nested email config.
        email_config = self._config_data.get('email', {})
        if name in email_config:
            return email_config[name]

        # Raise error if configuration key not found.
        raise AttributeError(f"'Config' object has no attribute '{name}'")

    def get_log_level(self) -> LogLevel:
        """
        Returns the LogLevel enum based on the log_level config value.
        Validates the configured level and defaults to INFO if invalid.

        Returns:
            LogLevel: The configured log level (defaults to INFO if invalid).
        """
        # Get logging configuration section.
        logging_config = self._config_data.get('logging', {})
        # Get log level string from config, default to INFO.
        level_str = logging_config.get('level', 'INFO').upper()
        try:
            # Convert string to LogLevel enum.
            return LogLevel[level_str]
        except KeyError:
            # Log warning and return default if invalid level.
            print(f"Warning: Invalid log level '{level_str}' in config. Using INFO.")
            return LogLevel.INFO

    def get_console_print(self) -> bool:
        """
        Returns whether console printing is enabled.
        Enables debug output to terminal in addition to log file.

        Returns:
            bool: True if console printing is enabled (default: True).
        """
        # Get logging configuration section.
        logging_config = self._config_data.get('logging', {})
        # Return console print setting with default of True.
        return logging_config.get('console_print', True)

    def is_email_enabled(self) -> bool:
        """
        Returns whether email alerting is enabled.
        When enabled, email reports are sent for listed IP addresses.

        Returns:
            bool: True if email alerting is enabled (default: False).
        """
        # Get email configuration section.
        email_config = self._config_data.get('email', {})
        # Return email enabled setting with default of False.
        return email_config.get('enabled', False)

    def get_email_recipients(self) -> list:
        """
        Returns the list of email recipients.
        Recipients will receive alerts when IP addresses are found on blacklists.

        Returns:
            list: List of email recipient addresses (default: empty list).
        """
        # Get email configuration section.
        email_config = self._config_data.get('email', {})
        # Return recipients list with default of empty list.
        return email_config.get('recipients', [])

    def get_email_sender(self) -> str:
        """
        Returns the email sender address.
        Used as the From field in alert emails.

        Returns:
            str: The sender email address (default: empty string).
        """
        # Get email configuration section.
        email_config = self._config_data.get('email', {})
        # Return sender email with default of empty string.
        return email_config.get('sender', '')

    def get_smtp_host(self) -> str:
        """
        Returns the SMTP host.
        Specifies the mail server for sending email alerts.

        Returns:
            str: The SMTP host (default: empty string).
        """
        # Get email configuration section.
        email_config = self._config_data.get('email', {})
        # Return SMTP host with default of empty string.
        return email_config.get('smtp_host', '')

    def get_smtp_port(self) -> int:
        """
        Returns the SMTP port.
        Standard SMTP port is 25, but 587 (TLS) and 465 (SSL) are also common.

        Returns:
            int: The SMTP port (default: 25).
        """
        # Get email configuration section.
        email_config = self._config_data.get('email', {})
        # Return SMTP port with default of 25.
        return email_config.get('smtp_port', 25)

    def get_smtp_user(self) -> str:
        """Return SMTP username for authentication (empty if not set)."""
        email_config = self._config_data.get('email', {})
        return email_config.get('smtp_user', '')

    def get_smtp_password(self) -> str:
        """Return SMTP password for authentication (empty if not set)."""
        email_config = self._config_data.get('email', {})
        return email_config.get('smtp_password', '')

    def get_smtp_use_tls(self) -> bool:
        """Return whether STARTTLS should be used."""
        email_config = self._config_data.get('email', {})
        return email_config.get('use_tls', False)

    def get_smtp_use_ssl(self) -> bool:
        """Return whether implicit SSL should be used (overrides TLS)."""
        email_config = self._config_data.get('email', {})
        return email_config.get('use_ssl', False)

    def get_nameservers(self) -> list:
        """
        Returns the list of DNS nameservers to use for DNSBL queries.
        Supports multiple nameservers for redundancy and load balancing.

        Returns:
            list: List of nameserver addresses (default: ['208.67.222.222']).
        """
        # Get nameservers list from config with default OpenDNS server.
        nameservers = self._config_data.get('nameservers', ['208.67.222.222'])
        # Ensure we have at least one nameserver.
        return nameservers if nameservers else ['208.67.222.222']

    def get_thread_count(self) -> int:
        """
        Returns the number of threads to use for concurrent DNSBL checks.
        More threads can improve performance but consume more resources.

        Returns:
            int: The number of threads (default: 10, minimum: 1).
        """
        # Get threading configuration section.
        threading_config = self._config_data.get('threading', {})
        # Get thread count with default of 10.
        thread_count = threading_config.get('thread_count', 10)
        # Ensure at least 1 thread is configured.
        return max(1, thread_count)

    def is_threading_enabled(self) -> bool:
        """
        Returns whether multithreading is enabled.
        When enabled, concurrent checks are performed using thread pools.

        Returns:
            bool: True if multithreading is enabled (default: True).
        """
        # Get threading configuration section.
        threading_config = self._config_data.get('threading', {})
        # Return threading enabled setting with default of True.
        return threading_config.get('enabled', True)

    def is_webhooks_enabled(self) -> bool:
        """
        Returns whether webhook alerting is enabled.
        When enabled, webhook notifications are sent for listed IP addresses.

        Returns:
            bool: True if webhook alerting is enabled (default: False).
        """
        # Get webhooks configuration section.
        webhooks_config = self._config_data.get('webhooks', {})
        # Return webhooks enabled setting with default of False.
        return webhooks_config.get('enabled', False)

    def get_webhook_urls(self) -> list:
        """
        Returns the list of webhook URLs to notify.
        Webhooks will receive alerts when IP addresses are found on blacklists.

        Returns:
            list: List of webhook URLs (default: empty list).
        """
        # Get webhooks configuration section.
        webhooks_config = self._config_data.get('webhooks', {})
        # Return webhook URLs list with default of empty list.
        return webhooks_config.get('urls', [])

    def get_webhook_timeout(self) -> int:
        """
        Returns the timeout for webhook requests in seconds.
        Specifies how long to wait for a webhook response before timing out.

        Returns:
            int: Timeout in seconds (default: 10).
        """
        # Get webhooks configuration section.
        webhooks_config = self._config_data.get('webhooks', {})
        # Return webhook timeout with default of 10 seconds.
        return webhooks_config.get('timeout', 10)


# Create a single instance of the Config class to be used throughout the application
config = Config()
