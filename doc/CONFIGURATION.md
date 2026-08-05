# Configuration

All runtime settings are loaded from YAML. Config selection order is:

1. A CLI path passed to `dnsblchk`, `main.py`, or a runner script.
2. The `DNSBLCHK_CONFIG` environment variable.
3. `/etc/dnsblchk/config.yaml`.
4. The repository sample at `config/config.yaml`.

## Core Settings

| Key | Type | Description |
| --- | --- | --- |
| `run_once` | bool | Exit after one check cycle. |
| `sleep_hours` | int | Hours between cycles when `run_once` is false. |
| `keep_last_reports` | int | Number of CSV reports to keep. |
| `rbls_file` | string | CSV/text file containing IP-based RBL zones. |
| `dbls_file` | string | CSV/text file containing domain-based DBL zones. |
| `ips_file` | string | CSV/text file containing IP addresses to check. |
| `report_dir` | string | Directory for CSV report output. |
| `nameservers` | list | DNS resolvers used for RBL, PTR, and DBL queries. |

For repository-style configs under `config/`, relative paths are resolved from
the current working directory first; the local runner scripts change into the
project root before starting the app. For custom configs outside the repository
config directory, paths next to the loaded YAML file are preferred.

## Address Groups

`address_groups` is optional. It maps labels to IP/CIDR entries. Matching labels
are written to the `obm_server` report column.

```yaml
address_groups:
  example-primary:
    - "192.0.2.0/24"
  example-secondary:
    - "198.51.100.0/24"
```

## Threading

```yaml
threading:
  enabled: true
  thread_count: 10
```

`thread_count` is clamped to a minimum of 1.
When `enabled` is false, checks run sequentially.

## Email

```yaml
email:
  enabled: false
  recipients:
    - "admin@example.com"
  sender: "dnsblchk@example.com"
  smtp_host: "localhost"
  smtp_port: 25
  smtp_user: ""
  smtp_password: ""
  use_tls: false
  use_ssl: false
```

Use environment-specific secret management for SMTP credentials instead of
committing real passwords.

## Webhooks

```yaml
webhooks:
  enabled: false
  urls:
    - "https://example.com/webhook"
  timeout: 10
```

The webhook client posts Slack-style Block Kit JSON with a plain text fallback.
No bot token or file-upload configuration is required by the open-source
project.

## API-Based IP Updates

```yaml
api_update:
  enabled: false
  url: "https://api.example.com/ips"
  auth_type: "none"
  username: ""
  password: ""
  bearer_token: ""
  timeout: 10
```

The API must return `text/plain` with one IP per line. If the update fails,
the configured `ips_file` list remains in use.

## Logging

```yaml
logging:
  level: "INFO"
  console_print: false
  log_dir: "logs/"
  log_file: "dnsblchk.log"
  clear_log_on_start: true
  run_log_dir: "logs/runs"
  keep_last_runs: 10
```
