import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from files import FileHandler


class TestFileHandler:
    """Test cases for FileHandler class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_log_error_creates_file(self, temp_dir):
        """Test that log_error creates a file if it doesn't exist."""
        error_file = temp_dir / "errors.log"
        FileHandler.log_error(error_file, "Test error")

        assert error_file.exists()
        content = error_file.read_text()
        assert "Test error" in content

    def test_log_error_appends_to_file(self, temp_dir):
        """Test that log_error appends to existing file."""
        error_file = temp_dir / "errors.log"
        FileHandler.log_error(error_file, "Error 1")
        FileHandler.log_error(error_file, "Error 2")

        content = error_file.read_text()
        assert "Error 1" in content
        assert "Error 2" in content
        lines = content.strip().split('\n')
        assert len(lines) == 2

    def test_log_error_includes_timestamp(self, temp_dir):
        """Test that log_error includes a timestamp."""
        error_file = temp_dir / "errors.log"
        FileHandler.log_error(error_file, "Test error")

        content = error_file.read_text()
        # Should contain format like "28 Oct 2025 12:00:00"
        assert " - " in content
        assert "Test error" in content

    def test_load_csv_simple(self, temp_dir):
        """Test loading a simple CSV file."""
        csv_file = temp_dir / "test.csv"

        # Create test CSV
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Age'])
            writer.writerow(['Alice', '30'])
            writer.writerow(['Bob', '25'])

        result = FileHandler.load_csv(csv_file)

        assert len(result) == 3
        assert result[0] == ['Name', 'Age']
        assert result[1] == ['Alice', '30']
        assert result[2] == ['Bob', '25']

    def test_load_csv_with_special_characters(self, temp_dir):
        """Test loading CSV with special characters and quotes."""
        csv_file = temp_dir / "test.csv"

        # Create test CSV with quoted fields
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f, quotechar='"')
            writer.writerow(['Name', 'Description'])
            writer.writerow(['Item 1', 'A description with, commas'])
            writer.writerow(['Item 2', 'Another "quoted" value'])

        result = FileHandler.load_csv(csv_file)

        assert len(result) == 3
        assert result[1][1] == 'A description with, commas'
        assert result[2][1] == 'Another "quoted" value'

    def test_load_csv_empty_file(self, temp_dir):
        """Test loading an empty CSV file."""
        csv_file = temp_dir / "empty.csv"
        csv_file.touch()

        result = FileHandler.load_csv(csv_file)

        assert result == []

    def test_load_csv_single_row(self, temp_dir):
        """Test loading CSV with only one row."""
        csv_file = temp_dir / "single.csv"

        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Single', 'Row'])

        result = FileHandler.load_csv(csv_file)

        assert len(result) == 1
        assert result[0] == ['Single', 'Row']

    def test_load_csv_with_empty_fields(self, temp_dir):
        """Test loading CSV with empty fields."""
        csv_file = temp_dir / "empty_fields.csv"

        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Field1', '', 'Field3'])
            writer.writerow(['', 'Value', ''])

        result = FileHandler.load_csv(csv_file)

        assert len(result) == 2
        assert result[0] == ['Field1', '', 'Field3']
        assert result[1] == ['', 'Value', '']

    def test_load_csv_multiline_fields(self, temp_dir):
        """Test loading CSV with multiline quoted fields."""
        csv_file = temp_dir / "multiline.csv"

        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f, quotechar='"')
            writer.writerow(['Name', 'Comments'])
            writer.writerow(['Test', 'Line 1\nLine 2\nLine 3'])

        result = FileHandler.load_csv(csv_file)

        assert len(result) == 2
        assert 'Line 1' in result[1][1]

    def test_timemark_format(self):
        """Test that _timemark returns formatted timestamp."""
        timemark = FileHandler._timemark()

        # Should be in format "28 Oct 2025 12:00:00"
        assert len(timemark) > 0
        parts = timemark.split()
        assert len(parts) >= 3
        # Check day is numeric
        assert parts[0].isdigit()

    @patch('files.time.strftime')
    def test_timemark_uses_gmt(self, mock_strftime):
        """Test that _timemark uses GMT time."""
        mock_strftime.return_value = "28 Oct 2025 12:00:00"
        timemark = FileHandler._timemark()

        mock_strftime.assert_called_once()
        call_args = mock_strftime.call_args
        # Should be called with time.gmtime()
        assert 'gmtime' in str(call_args) or call_args[0][0] == "%d %b %Y %H:%M:%S"

    def test_load_csv_with_different_delimiters(self, temp_dir):
        """Test that FileHandler uses comma as delimiter."""
        csv_file = temp_dir / "test.csv"

        with open(csv_file, 'w', newline='') as f:
            f.write('a,b,c\n')
            f.write('1,2,3\n')

        result = FileHandler.load_csv(csv_file)

        assert result[0] == ['a', 'b', 'c']
        assert result[1] == ['1', '2', '3']

    def test_log_error_multiple_calls(self, temp_dir):
        """Test multiple calls to log_error."""
        error_file = temp_dir / "errors.log"

        for i in range(5):
            FileHandler.log_error(error_file, f"Error message {i}")

        content = error_file.read_text()
        lines = content.strip().split('\n')

        assert len(lines) == 5
        for i in range(5):
            assert f"Error message {i}" in content
