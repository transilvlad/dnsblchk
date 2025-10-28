import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from logger import Logger, LogConfig, LogLevel


class TestLogLevel:
    """Test cases for LogLevel enum."""

    def test_log_level_values(self):
        """Test that log levels have correct integer values."""
        assert LogLevel.DEBUG.value == 0
        assert LogLevel.INFO.value == 1
        assert LogLevel.WARN.value == 2
        assert LogLevel.ERROR.value == 3

    def test_log_level_comparison(self):
        """Test that log levels can be compared."""
        assert LogLevel.DEBUG.value < LogLevel.INFO.value
        assert LogLevel.ERROR.value > LogLevel.WARN.value


class TestLogConfig:
    """Test cases for LogConfig class."""

    def test_log_config_defaults(self):
        """Test LogConfig initialization with default values."""
        config = LogConfig()
        assert config.log_file is None
        assert config.log_dir is None
        assert config.level == LogLevel.INFO
        assert config.console_print is True

    def test_log_config_custom_values(self):
        """Test LogConfig initialization with custom values."""
        log_file = Path("/tmp/test.log")
        log_dir = Path("/tmp")
        config = LogConfig(
            log_file=log_file,
            log_dir=log_dir,
            level=LogLevel.DEBUG,
            console_print=False
        )
        assert config.log_file == log_file
        assert config.log_dir == log_dir
        assert config.level == LogLevel.DEBUG
        assert config.console_print is False


class TestLogger:
    """Test cases for Logger class."""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def logger_with_file(self, temp_log_dir):
        """Create a logger instance with a temporary log file."""
        log_file = temp_log_dir / "test.log"
        config = LogConfig(
            log_file=log_file,
            log_dir=temp_log_dir,
            level=LogLevel.DEBUG,
            console_print=False
        )
        return Logger(config), log_file

    def test_logger_initialization(self, temp_log_dir):
        """Test logger initialization."""
        config = LogConfig(log_dir=temp_log_dir, level=LogLevel.INFO)
        logger = Logger(config)
        assert logger.config == config
        assert temp_log_dir.exists()

    def test_log_error(self, logger_with_file):
        """Test logging an error message."""
        logger, log_file = logger_with_file
        logger.log_error("Test error message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "ERROR" in content
        assert "Test error message" in content

    def test_log_info(self, logger_with_file):
        """Test logging an info message."""
        logger, log_file = logger_with_file
        logger.log_info("Test info message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "INFO" in content
        assert "Test info message" in content

    def test_log_warning(self, logger_with_file):
        """Test logging a warning message."""
        logger, log_file = logger_with_file
        logger.log_warning("Test warning message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "WARN" in content
        assert "Test warning message" in content

    def test_log_debug(self, logger_with_file):
        """Test logging a debug message."""
        logger, log_file = logger_with_file
        logger.log_debug("Test debug message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "DEBUG" in content
        assert "Test debug message" in content

    def test_log_level_filtering(self, temp_log_dir):
        """Test that log messages are filtered by level."""
        log_file = temp_log_dir / "test.log"
        config = LogConfig(
            log_file=log_file,
            log_dir=temp_log_dir,
            level=LogLevel.WARN,
            console_print=False
        )
        logger = Logger(config)

        logger.log_debug("Debug message")
        logger.log_info("Info message")
        logger.log_warning("Warning message")
        logger.log_error("Error message")

        content = log_file.read_text()
        assert "Debug message" not in content
        assert "Info message" not in content
        assert "Warning message" in content
        assert "Error message" in content

    def test_console_print_disabled(self, temp_log_dir):
        """Test that console print can be disabled."""
        log_file = temp_log_dir / "test.log"
        config = LogConfig(
            log_file=log_file,
            log_dir=temp_log_dir,
            console_print=False
        )
        logger = Logger(config)

        with patch('builtins.print') as mock_print:
            logger.log_info("Test message")
            mock_print.assert_not_called()

    def test_console_print_enabled(self, temp_log_dir):
        """Test that console print works when enabled."""
        log_file = temp_log_dir / "test.log"
        config = LogConfig(
            log_file=log_file,
            log_dir=temp_log_dir,
            console_print=True
        )
        logger = Logger(config)

        with patch('builtins.print') as mock_print:
            logger.log_info("Test message")
            mock_print.assert_called_once()
            assert "Test message" in str(mock_print.call_args)

    def test_log_without_file(self, temp_log_dir):
        """Test logging without a log file (should not crash)."""
        config = LogConfig(
            log_file=None,
            log_dir=temp_log_dir,
            console_print=False
        )
        logger = Logger(config)
        # Should not raise an exception
        logger.log_info("Test message")
        logger.log_error("Test error")

    def test_create_log_directory(self, temp_log_dir):
        """Test that log directory is created if it doesn't exist."""
        nested_dir = temp_log_dir / "nested" / "logs"
        config = LogConfig(
            log_dir=nested_dir,
            console_print=False
        )
        logger = Logger(config)
        assert nested_dir.exists()

    @patch('logger.time.strftime')
    def test_timemark_format(self, mock_strftime, temp_log_dir):
        """Test that timestamps are formatted correctly."""
        mock_strftime.return_value = "28 Oct 2025 12:00:00"
        log_file = temp_log_dir / "test.log"
        config = LogConfig(
            log_file=log_file,
            log_dir=temp_log_dir,
            console_print=False
        )
        logger = Logger(config)
        logger.log_info("Test message")

        content = log_file.read_text()
        assert "28 Oct 2025 12:00:00" in content
