import csv
import time
from pathlib import Path
from typing import List


class FileHandler:
    """Handles file operations including CSV loading and error logging."""

    @staticmethod
    def log_error(file_name: Path, data: str):
        """Appends a timestamped error message to the specified log file."""
        with open(file_name, 'a') as error_log:
            error_log.write(f"{FileHandler._timemark()} - {data}\n")

    @staticmethod
    def load_csv(file_path: Path) -> List[List[str]]:
        """Loads all data from a CSV file."""
        result = []
        with open(file_path, 'r', newline='') as csvfile:
            csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
            for row in csvreader:
                result.append(row)
        return result

    @staticmethod
    def _timemark() -> str:
        """Returns the current time formatted as a string."""
        return time.strftime("%d %b %Y %H:%M:%S", time.gmtime())
