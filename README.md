# DNS Block List Checker (DNSblChk)

DNSblChk is an open-source Python script and service for monitoring and reporting on DNS blacklists.
It is designed for ease of use, with a straightforward configuration and clear reporting.

## Features

-   **Easy Configuration**: All settings are managed in a single `config/config.yaml` file.
-   **CSV Reports**: Records all findings in CSV files for easy analysis.
-   **Email Alerts**: Sends detailed email notifications when listed IP addresses are found.
-   **Flexible Operation**: Can be run as a continuous monitoring service or as a one-time check.
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

## Packaging

For instructions on how to package the application into an RPM,
please see the [Packaging Guide](PACKAGING.md).

## Configuration

All configuration is done in the `config.yaml` file. Here are the available options:

### General Settings
-   `run_once`: If `true`, the script will run once and then exit. (Default: `false`)
-   `sleep_hours`: The number of hours to wait between checks. (Default: `3`)

### File Paths
-   `servers_file`: Path to the CSV file containing DNSBL servers.
-   `ips_file`: Path to the CSV file containing IPs to check.
-   `report_dir`: Directory to store CSV report files from DNSBL checks.

### DNS Nameservers
-   `nameservers`: A list of DNS nameservers to use for DNSBL queries.
    - Supports multiple servers for redundancy and load balancing.
    - Example: `['208.67.222.222', '208.67.220.220']` (OpenDNS servers)
    - If not specified, defaults to `['208.67.222.222']`

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
-   `email.smtp_user`: (Optional) Username for SMTP authentication. Leave blank if not required.
-   `email.smtp_password`: (Optional) Password for SMTP authentication. Leave blank if not required.
-   `email.use_tls`: If `true`, enables STARTTLS after connecting (typical for port 587).
-   `email.use_ssl`: If `true`, uses implicit SSL (typical for port 465). Overrides `use_tls` if both are `true`.

Security tip: Prefer environment-specific secrets management (e.g., Ansible Vault, Kubernetes secrets)
to store `smtp_password` instead of committing plain text to version control.

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

## Docker Usage

You can run dnsblchk in a container.
The image is published to GitHub Container Registry (GHCR) on release.

### Build Locally

```bash
docker build -t dnsblchk:local .
```

### Run Locally (Manual)

Mount the `config` and `logs` directories so they persist and can be edited without rebuilding the image.

```bash
mkdir -p config logs
# Ensure config/config.yaml exists (copy template if needed)
cp config/config.yaml.template config/config.yaml
# Edit config/config.yaml as desired.

docker run --rm \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/logs:/app/logs" \
  dnsblchk:local
```

### Using docker-compose

A `docker-compose.yml` is included:

```bash
docker compose up -d --build
docker compose logs -f
```

Edit `config/config.yaml` locally; the container picks up changes automatically on next cycle.

### Published Image

On release tags, GitHub Actions builds and pushes multi-arch images to:

```
ghcr.io/transilvlad/dnsblchk:latest
ghcr.io/transilvlad/dnsblchk:<tag>
```

Pull and run:

```bash
docker pull ghcr.io/transilvlad/dnsblchk:latest
docker run -d --name dnsblchk \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/logs:/app/logs" \
  ghcr.io/transilvlad/dnsblchk:latest
```

### Configuration & Logs

- Config volume mount: `./config` -> `/app/config`
- Logs volume mount: `./logs` -> `/app/logs`

Adjust `config.yaml` to disable `run_once` for continuous operation.

### Updating

Pull the latest image and recreate the compose service:

```bash
docker compose pull
docker compose up -d
docker image prune -f
```
