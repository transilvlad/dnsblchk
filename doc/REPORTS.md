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

### The Slack summary counts two separate populations

This is the single most misread part of the report, so it is worth stating
plainly. A run tracks two different kinds of thing, and they never mix:

| Population | What is counted | Where it comes from |
| --- | --- | --- |
| **IPs listed on RBLs** | source IPs | `IP` rows — the IP itself is listed |
| **Domains listed on DBLs** | domain names | `PTR` / `APEX` rows — a *hostname* the IP resolves to is listed |

An IP with no `IP` row is **not** counted in the IP total, even if its PTR is
on a DBL. Such IPs are reported separately as "affecting N IPs" and, when they
come clean, as "IPs no longer pointing at a listed domain" — never as delisted
IPs.

Both populations report their own previous-run figure, so each block is
self-checking:

```text
total = previous + newly listed - delisted
```

If that identity ever fails, `_send_categorized_notifications` logs
`Summary arithmetic inconsistent` at ERROR level rather than posting a message
that contradicts itself.

### Delta baseline

The delta is computed against **what the previous run alerted on**, not against
the raw previous CSV. The CSV also contains DBL sightings the previous run was
still holding behind the `require_consecutive_runs` persistence gate (see
`dbl_pending.json`). Those were never announced as listed, so they must not be
announced as delisted — `_strip_held_sightings` removes them from the baseline.

Because the CSV is the delta baseline, it has to be a lossless carrier for the
server labels above: `_load_previous_results` rebuilds the ` [source:target]`
suffix from the `check_type` / `target` / `target_source` columns. Reading only
the bare `server` column makes every DBL sighting indistinguishable from an RBL
listing, which is what once produced reports like "13 delisted IPs" alongside
an unchanged total of "153 IPs listed".
