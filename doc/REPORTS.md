# Reports

dnsblchk writes a CSV report only when a listing is found. Reports are created in
`report_dir` with names like `report_YYYYMMDDHHMMSS.csv`.

## Columns

```csv
timestamp,source_ip,check_type,target,target_source,server,obm_server,response,txt_context
```

| Column | Description |
| --- | --- |
| `timestamp` | UTC time when the row was written. |
| `source_ip` | IP address from `ips_file` or the API update. |
| `check_type` | `IP`, `PTR`, or `APEX`. |
| `target` | Actual IP or domain queried. |
| `target_source` | `ip`, `ptr`, or `apex`. |
| `server` | RBL or DBL zone that returned a listing. |
| `obm_server` | Optional address group label from config. |
| `response` | DNS A response code, such as `127.0.0.2`. |
| `txt_context` | Optional TXT context returned by DBL zones. |

## RBL Checks

For `IP` rows, dnsblchk reverses the source IP and queries each configured RBL
zone. Example for `192.0.2.10`:

```text
10.2.0.192.zen.spamhaus.org
```

## DBL Checks

For DBL checks, dnsblchk first resolves the source IP's PTR hostname. If a PTR
exists, it checks:

- The PTR hostname as `PTR`.
- The registrable apex as `APEX`, when different from the PTR hostname.

Example:

```text
PTR:  mail.example.com
APEX: example.com
```

If there is no PTR hostname, no DBL checks are scheduled for that IP.

## Notifications

Email and webhook notifications summarize listed source IPs. DBL listings are
included as labels such as:

```text
dbl.example.com [ptr:mail.example.com]
dbl.example.com [apex:example.com]
```
