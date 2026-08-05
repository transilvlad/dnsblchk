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

    def test_debug_directory_creation_message(self, tmp_path):
        """Test debug console message when creating a log directory."""
        nested_dir = tmp_path / "nested" / "logs"
        config = LogConfig(log_dir=nested_dir, level=LogLevel.DEBUG, console_print=True)

        with patch("builtins.print") as mocked_print:
            Logger(config)

        mocked_print.assert_called_once()
        assert "Created log directory" in mocked_print.call_args.args[0]

    def test_start_run_creates_run_file_and_latest_symlink(self, temp_log_dir):
        """Test start/end run writes run logs and updates latest symlink."""
        run_dir = temp_log_dir / "runs"
        log_file = temp_log_dir / "dnsblchk.log"
        logger = Logger(LogConfig(
            log_file=log_file,
            log_dir=temp_log_dir,
            run_log_dir=run_dir,
            console_print=False,
        ))

        logger.start_run()
        assert logger.run_file_handle is not None
        run_file = run_dir / f"run-{logger.current_run_id}.log"
        latest_link = temp_log_dir / "latest-run.log"
        logger.log_info("message for run")
        logger.end_run()

        content = run_file.read_text(encoding="utf-8")
        assert "Run started" in content
        assert "message for run" in content
        assert "Run ended" in content
        assert latest_link.is_symlink()

    def test_start_run_without_run_dir_is_noop(self, temp_log_dir):
        """Test start_run returns when no per-run log directory is configured."""
        logger = Logger(LogConfig(log_dir=temp_log_dir, console_print=False))

        logger.start_run()

        assert logger.run_file_handle is None
        assert logger.current_run_id is None

    def test_start_run_reports_open_failure(self, temp_log_dir):
        """Test start_run handles file open failures."""
        logger = Logger(LogConfig(run_log_dir=temp_log_dir / "runs", console_print=True))

        with patch("builtins.open", side_effect=OSError("denied")), patch("builtins.print") as mocked_print:
            logger.start_run()

        assert logger.run_file_handle is None
        assert "Failed to start run file" in mocked_print.call_args.args[0]

    def test_start_run_reports_symlink_failure(self, temp_log_dir):
        """Test start_run keeps logging even if latest symlink cannot be created."""
        logger = Logger(LogConfig(run_log_dir=temp_log_dir / "runs", console_print=True))

        with patch("pathlib.Path.symlink_to", side_effect=OSError("no symlink")), patch("builtins.print") as mocked_print:
            logger.start_run()

        try:
            assert "Failed to create symlink" in mocked_print.call_args.args[0]
        finally:
            logger.end_run()

    def test_end_run_handles_close_failure(self, temp_log_dir):
        """Test end_run reports close/write failures and clears state."""
        logger = Logger(LogConfig(run_log_dir=temp_log_dir / "runs", console_print=True))
        logger.run_file_handle = MagicHandle(write_error=OSError("write failed"))
        logger.current_run_id = "20200101_000000_000"

        with patch("builtins.print") as mocked_print:
            logger.end_run()

        assert logger.run_file_handle is None
        assert logger.current_run_id is None
        assert "Failed to close run file" in mocked_print.call_args.args[0]

    def test_log_to_run_file_handles_write_failure(self, temp_log_dir):
        """Test run-file write failures are reported when console printing is enabled."""
        logger = Logger(LogConfig(run_log_dir=temp_log_dir / "runs", console_print=True))
        logger.run_file_handle = MagicHandle(write_error=OSError("write failed"))

        with patch("builtins.print") as mocked_print:
            logger._log_to_run_file("message")

        assert "Failed to write to run file" in mocked_print.call_args.args[0]

    def test_cleanup_old_runs_deletes_oldest_files(self, temp_log_dir):
        """Test run retention keeps only the newest configured files."""
        run_dir = temp_log_dir / "runs"
        run_dir.mkdir()
        old = run_dir / "run-20200101_000000_000.log"
        mid = run_dir / "run-20200102_000000_000.log"
        new = run_dir / "run-20200103_000000_000.log"
        for path in (old, mid, new):
            path.write_text("run\n", encoding="utf-8")

        logger = Logger(LogConfig(run_log_dir=run_dir, keep_last_runs=2, console_print=False))
        logger._cleanup_old_runs()

        assert not old.exists()
        assert mid.exists()
        assert new.exists()

    def test_cleanup_old_runs_reports_failure(self, temp_log_dir):
        """Test cleanup failures are reported when console printing is enabled."""
        run_dir = temp_log_dir / "runs"
        run_dir.mkdir()
        (run_dir / "run-20200101_000000_000.log").write_text("run\n", encoding="utf-8")
        (run_dir / "run-20200102_000000_000.log").write_text("run\n", encoding="utf-8")
        logger = Logger(LogConfig(run_log_dir=run_dir, keep_last_runs=1, console_print=True))

        with patch("pathlib.Path.unlink", side_effect=OSError("cannot delete")), patch("builtins.print") as mocked_print:
            logger._cleanup_old_runs()

        assert "Failed to cleanup old run files" in mocked_print.call_args.args[0]


class MagicHandle:
    def __init__(self, write_error=None):
        self.write_error = write_error

    def write(self, _message):
        if self.write_error:
            raise self.write_error

    def flush(self):
        return None
