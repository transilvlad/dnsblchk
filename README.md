# DNSblChk

DNSblChk is a modern, open-source Python service for monitoring and reporting on DNS blacklists. It is designed for ease of use, with a straightforward configuration and clear reporting.

## Features

-   **Modern Python**: Refactored for Python 3 with type hints and current best practices.
-   **Easy Configuration**: All settings are managed in a single `config/config.yaml` file.
-   **CSV Reports**: Records all findings in CSV files for easy analysis.
-   **Email Alerts**: Sends detailed email notifications when listed IP addresses are found.
-   **Flexible Operation**: Can be run as a continuous monitoring service or as a one-time check.
-   **Multithreading Support**: Run DNSBL checks across multiple threads for improved performance.
-   **Advanced Logging**: Configurable logging levels (DEBUG, INFO, WARN, ERROR) with console and file output control.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/transilvlad/dnsblchk.git
    cd dnsblchk
    ```

2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

All configuration is done in the `config.yaml` file. Here are the available options:

### General Settings
-   `run_once`: If `true`, the script will run once and then exit. (Default: `false`)
-   `sleep_hours`: The number of hours to wait between checks. (Default: `3`)

### File Paths
-   `servers_file`: Path to the CSV file containing DNSBL servers.
-   `ips_file`: Path to the CSV file containing IPs to check.
-   `report_dir`: Directory to store CSV report files from DNSBL checks.

### Threading Settings
-   `threading.enabled`: If `true`, multithreading is enabled for DNSBL checks. (Default: `true`)
-   `threading.thread_count`: The number of worker threads to use for concurrent checks. (Default: `4`, Minimum: `1`)
    - Increase this value for faster checks but higher resource usage.
    - Decrease for lower resource usage but slower checks.

### Email Alerting
-   `email.enabled`: If `true`, an email report will be sent if any IPs are listed. (Default: `false`)
-   `email.recipients`: A list of email addresses to receive alerts.
-   `email.sender`: The "From" address for email alerts.
-   `email.smtp_host`: The hostname or IP address of your SMTP server.
-   `email.smtp_port`: The port for your SMTP server. (Default: `25`)

### Logging Settings
-   `logging.level`: Logging level for the application. Can be `DEBUG`, `INFO`, `WARN`, or `ERROR`. (Default: `INFO`)
-   `logging.console_print`: If `true`, log messages will be printed to console in addition to the log file. (Default: `true`)
-   `logging.log_dir`: Directory to store log files.
-   `logging.log_file`: Path to the main log file for logging errors and events.

## Usage

To run the service, simply execute the `main.py` script:

```bash
python main.py
```

The service will start checking the IPs listed in `config/ips.txt` against the DNSBL servers in `config/servers.txt`.
Any findings will be logged and to a CSV file and if configured, email alerts will be sent.
