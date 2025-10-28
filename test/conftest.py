import tempfile
from pathlib import Path

import pytest

from logger import Logger, LogConfig, LogLevel


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_log_file(temp_dir):
    """Create a temporary log file path."""
    return temp_dir / "test.log"


@pytest.fixture
def temp_log_dir(temp_dir):
    """Create a temporary log directory."""
    log_dir = temp_dir / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def logger_config(temp_log_dir):
    """Create a logger configuration for testing."""
    return LogConfig(
        log_file=temp_log_dir / "test.log",
        log_dir=temp_log_dir,
        level=LogLevel.DEBUG,
        console_print=False
    )


@pytest.fixture
def logger(logger_config):
    """Create a logger instance for testing."""
    return Logger(logger_config)


@pytest.fixture
def temp_csv_file(temp_dir):
    """Create a path for a temporary CSV file."""
    return temp_dir / "test.csv"

