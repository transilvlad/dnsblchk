# DNS RBL Checker

An open-source Python script and service for monitoring and reporting on DNS RBLs.
It is designed for ease of use, with a straightforward configuration and clear reporting.

## Features

-   **Easy Configuration**: All settings are managed in a single `config/config.yaml` file.
-   **CSV Reports**: Records all findings in CSV files for easy analysis.
-   **Email Alerts**: Sends detailed email notifications when listed IP addresses are found.
-   **Webhook Notifications**: Posts alerts to external services (Slack, Discord, custom APIs) for integration flexibility.
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
-   `servers_file`: Path to the CSV file containing RBL servers.
-   `ips_file`: Path to the CSV file containing IPs to check.
-   `report_dir`: Directory to store CSV report files from RBL checks.

### DNS Nameservers
-   `nameservers`: A list of DNS nameservers to use for RBL queries.
    - Supports multiple servers for redundancy and load balancing.
    - Example: `['208.67.222.222', '208.67.220.220']` (OpenDNS servers)
    - If not specified, defaults to `['208.67.222.222']`

### Threading Settings
-   `threading.enabled`: If `true`, multithreading is enabled for RBL checks. (Default: `true`)
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

### Webhook Alerting
-   `webhooks.enabled`: If `true`, webhook notifications will be sent when IPs are listed. (Default: `false`)
-   `webhooks.urls`: A list of webhook URLs to post notifications to. Supports multiple URLs for redundancy.
    - Example: `['https://hooks.slack.com/services/YOUR/WEBHOOK', 'https://your-api.example.com/alerts']`
    - Default: `[]` (empty list)
-   `webhooks.timeout`: Timeout in seconds for webhook HTTP requests. (Default: `10`)

Webhooks use Slack-compatible JSON payload format and can be used with Slack, Discord, or any custom HTTP endpoint:
```json
{
  "text": "DNS RBL Alert\n--------------------\n\nListed IPs: 1\n\n192.168.1.1 ===> server1, server2\n",
}
```

Examples: Slack (`https://hooks.slack.com/services/...`), Discord (`https://discordapp.com/api/webhooks/...`), or any custom HTTP endpoint.

### API-Based IP Update
-   `api_update.enabled`: If `true`, IP addresses will be fetched from an API before each check run. (Default: `false`)
-   `api_update.url`: API endpoint URL that returns a text/plain response with one IP address per line.
    - Example: `https://api.example.com/ips`
    - The API must return a text/plain response with IP addresses separated by newlines
    - If the API fetch fails, the existing `ips.txt` file will be used as fallback
-   `api_update.auth_type`: Authentication type for the API. Options: `none`, `basic`, `bearer` (Default: `none`)
-   `api_update.username`: Username for basic authentication (required if `auth_type` is `basic`)
-   `api_update.password`: Password for basic authentication (required if `auth_type` is `basic`)
-   `api_update.bearer_token`: Bearer token for bearer authentication (required if `auth_type` is `bearer`)
-   `api_update.timeout`: Timeout in seconds for API requests. (Default: `10`)

Example API response (text/plain):
```
192.168.1.1
10.0.0.1
172.16.0.1
```

**Note**: The API update feature allows you to dynamically update the list of IP addresses to check from an external source before each check cycle. This is useful for monitoring dynamic IP ranges or integrating with external inventory systems.

Security tip: Use environment-specific secrets management for `password` and `bearer_token` instead of committing them to version control.

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

The service will start checking the IPs listed in `config/ips.txt` against the RBL servers in `config/servers.txt`.
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
