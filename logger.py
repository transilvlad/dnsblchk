import time
from enum import Enum
from pathlib import Path
from typing import Optional


class LogLevel(Enum):
    """Enumeration for logging levels."""
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


class LogConfig:
    """Configuration object for logging."""

    def __init__(
        self,
        log_file: Optional[Path] = None,
        log_dir: Optional[Path] = None,
        level: LogLevel = LogLevel.INFO,
        console_print: bool = True,
    ):
        """
        Initialize the log configuration.

        Args:
            log_file: Path to the log file. If None, no logging to file will occur.
            log_dir: Path to the log directory. Will be created if it doesn't exist.
            level: Logging level (DEBUG, INFO, WARN, ERROR). Defaults to INFO.
            console_print: Enable printing logs to console. Defaults to True.
        """
        self.log_file = log_file
        self.log_dir = log_dir
        self.level = level
        self.console_print = console_print


class Logger:
    """Handles logging of errors and other messages to log files."""

    def __init__(self, config: LogConfig):
        """
        Initialize the logger with a LogConfig object.

        Args:
            config: LogConfig object containing logging configuration.
        """
        self.config = config

        # Create log directory if provided
        if self.config.log_dir:
            self._create_log_directory(self.config.log_dir)

    def log_error(self, message: str) -> None:
        """
        Logs an error message to a file with a timestamp.

        Args:
            message: The error message to log.
        """
        if self.config.level.value <= LogLevel.ERROR.value:
            self._log("ERROR", message)

    def log_info(self, message: str) -> None:
        """
        Logs an info message to a file with a timestamp.

        Args:
            message: The info message to log.
        """
        if self.config.level.value <= LogLevel.INFO.value:
            self._log("INFO", message)

    def log_warning(self, message: str) -> None:
        """
        Logs a warning message to a file with a timestamp.

        Args:
            message: The warning message to log.
        """
        if self.config.level.value <= LogLevel.WARN.value:
            self._log("WARN", message)

    def log_debug(self, message: str) -> None:
        """
        Logs a debug message to a file with a timestamp (only if debug mode is enabled).

        Args:
            message: The debug message to log.
        """
        if self.config.level.value <= LogLevel.DEBUG.value:
            self._log("DEBUG", message)

    def _log(self, log_type: str, message: str, log_file: Optional[Path] = None) -> None:
        """
        Internal method to handle all logging with consistent formatting.

        Args:
            log_type: The type of log (ERROR, INFO, WARN, DEBUG, etc.).
            message: The message to log.
            log_file: Optional override for the log file path.
        """
        file_path = log_file or self.config.log_file
        if not file_path:
            return

        timestamp = self._timemark()
        log_message = f"{log_type} - {timestamp}: {message}"

        # Write to file
        with open(file_path, 'a') as f:
            f.write(log_message + "\n")

        # Print to console if enabled
        if self.config.console_print:
            print(log_message)

    def _create_log_directory(self, log_dir: Path) -> None:
        """
        Creates the log directory if it doesn't exist.
        Logs a debug message if the directory is created.

        Args:
            log_dir: Path to the log directory.
        """
        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
            if self.config.level.value <= LogLevel.DEBUG.value and self.config.console_print:
                print(f"[DEBUG] Created log directory: {log_dir}")

    @staticmethod
    def _timemark() -> str:
        """Returns the current time formatted as a string in GMT."""
        # Format current time in GMT format for consistent logging timestamps.
        return time.strftime("%d %b %Y %H:%M:%S", time.gmtime())
        return time.strftime("%d %b %Y %H:%M:%S", time.gmtime())
