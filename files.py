import csv
import time
from pathlib import Path
from typing import List


class FileHandler:
    """Handles file operations including CSV loading and error logging."""

    @staticmethod
    def log_error(file_name: Path, data: str):
        """
        Appends a timestamped error message to the specified log file.

        Args:
            file_name: Path to the error log file.
            data: Error message to append.
        """
        # Open file in append mode to add error at end.
        with open(file_name, 'a') as error_log:
            # Write timestamp and error message on new line.
            error_log.write(f"{FileHandler._timemark()} - {data}\n")

    @staticmethod
    def load_csv(file_path: Path) -> List[List[str]]:
        """
        Loads all data from a CSV file and returns as list of lists.
        Each row is preserved as a separate list.

        Args:
            file_path: Path to the CSV file to load.

        Returns:
            List of rows, where each row is a list of strings.
        """
        # Initialize empty result list.
        result = []
        # Open CSV file for reading.
        with open(file_path, 'r', newline='') as csvfile:
            # Create CSV reader with comma delimiter and double quote character.
            csvreader = csv.reader(csvfile, delimiter=',', quotechar='"')
            # Iterate through all rows in the CSV file.
            for row in csvreader:
                # Append each row to result list.
                result.append(row)
        # Return complete list of rows.
        return result

    @staticmethod
    def _timemark() -> str:
        """Returns the current time formatted as a string in GMT."""
        # Format current time in GMT for consistent timestamps in error logs.
        return time.strftime("%d %b %Y %H:%M:%S", time.gmtime())
