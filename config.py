from pathlib import Path

import yaml

from logger import LogLevel


class Config:
    """
    Handles loading the configuration from config.yaml and provides access to the settings.
    Supports nested configuration sections for logging, email, and threading.
    """

    def __init__(self):
        """Loads the configuration from config.yaml and resolves file paths."""
        # Get the root directory of the application.
        root_path = Path(__file__).parent
        # Construct path to configuration file.
        config_path = root_path / 'config/config.yaml'

        # Load YAML configuration file.
        with open(config_path, 'r') as f:
            self._config_data = yaml.safe_load(f)

        # Resolve all relative file paths to absolute paths.
        self._resolve_paths()

    def _resolve_paths(self):
        """Resolves all file paths in the config to be absolute."""
        # Resolve servers file path to absolute.
        self._config_data['servers_file'] = self._get_absolute_path('servers_file')
        # Resolve IPs file path to absolute.
        self._config_data['ips_file'] = self._get_absolute_path('ips_file')
        # Resolve report directory path to absolute.
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
                root_path = Path(__file__).parent
                abs_log_dir = root_path / log_dir
                # Store the combined absolute path.
                logging_config['log_file'] = abs_log_dir / log_filename
            else:
                # Fallback to old behavior if either is missing.
                logging_config['log_file'] = self._get_absolute_path_from_logging('log_file')

    def _get_absolute_path(self, key: str) -> Path:
        """Returns an absolute path for a given config key."""
        # Get application root directory.
        root_path = Path(__file__).parent
        # Combine with relative path from config.
        return root_path / self._config_data[key]

    def _get_absolute_path_from_logging(self, key: str) -> Path:
        """Returns an absolute path for a given key in the logging config."""
        # Get application root directory.
        root_path = Path(__file__).parent
        # Get logging configuration section.
        logging_config = self._config_data.get('logging', {})
        # Combine root with relative path from logging config.
        return root_path / logging_config[key]

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


# Create a single instance of the Config class to be used throughout the application
config = Config()
