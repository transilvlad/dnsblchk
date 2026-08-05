![DNS Block List Checker](doc/splash.jpg)

# DNS Block List Checker

`dnsblchk` is an open-source Python service for monitoring IP addresses and
derived domains against DNS block lists. It performs IP-based RBL checks and
domain-based DBL checks, writes structured CSV reports, and can notify by email
or webhook.

## Features

- RBL checks for IP addresses from `config/ips.txt`.
- DBL checks for PTR hostnames and registrable apex domains derived from those IPs.
- Structured CSV reports with `IP`, `PTR`, and `APEX` rows.
- Email and webhook notifications.
- Optional API-based IP list refresh before each run.
- Local runner scripts for Linux/macOS/WSL, Windows, and cross-platform Python.
- Docker, RPM, and DEB deployment support.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

For Windows:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
run.bat
```

## Minimal Configuration

```yaml
run_once: true
rbls_file: "config/rbls.txt"
dbls_file: "config/dbls.txt"
ips_file: "config/ips.txt"
report_dir: "logs/"
nameservers:
  - "208.67.222.222"
  - "208.67.220.220"
```

The tracked local config uses relative paths and run-once mode. The default
checked IP list uses documentation-reserved addresses. Replace
`config/ips.txt` with the IPs you want to monitor.

## Running

```bash
python main.py config/config-local.yaml
./run.sh --config config/config-local.yaml
python run.py --config config/config-local.yaml
dnsblchk /etc/dnsblchk/config.yaml
```

Docker:

```bash
docker compose up -d
docker compose logs -f
```

## Documentation

- [Documentation Guide](doc/DOCUMENTATION_GUIDE.md): where to start.
- [Quick Start](doc/QUICKSTART.md): local setup and first run.
- [Configuration](doc/CONFIGURATION.md): full config reference.
- [Reports](doc/REPORTS.md): CSV output, RBL/DBL behavior, and notifications.
- [Runner Scripts](doc/RUNNER_SCRIPTS.md): `run.sh`, `run.bat`, and `run.py`.
- [Packaging](doc/PACKAGING.md): RPM, DEB, Docker, and release builds.

## Packaging

The package version is defined in `pyproject.toml`. Build a Debian package with:

```bash
bash build-deb.sh
```

See [doc/PACKAGING.md](doc/PACKAGING.md) for complete packaging instructions.

## Contributing

Run the test suite before submitting changes:

```bash
PYTHONPATH=. pytest -q
PYTHONPATH=. pytest --cov -q
```
