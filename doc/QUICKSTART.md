# Quick Start

Get dnsblchk running locally with the sample configuration.

## Prerequisites

- Python 3.14.6 or newer.
- `pip`.

## Setup

Linux, macOS, or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows Command Prompt:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configure

Edit the tracked local profile, `config/config-local.yaml`:

- Set `run_once: true` for a single local test run.
- Keep `rbls_file` pointed at `config/rbls.txt`.
- Keep `dbls_file` pointed at `config/dbls.txt`.
- Replace `config/ips.txt` with the IP addresses you want to check.
- Leave email and webhooks disabled until DNS checks behave as expected.

## Run

Use one of the local runners:

```bash
python run.py
./run.sh
```

On Windows:

```cmd
run.bat
```

Or call the app directly:

```bash
python main.py config/config-local.yaml
```

## Extended Or Custom Configs

The runners accept a custom config path:

```bash
python run.py --config config/custom.yaml
./run.sh --config config/custom.yaml
```

They also support `--extended`, which expects `config/config-local-extended.yaml`.
Create that file from `config/config-local.yaml` if you want a second local profile.

## Troubleshooting

- `Config file not found`: restore `config/config-local.yaml` or pass `--config`.
- `Python 3.14+ not found`: activate your virtual environment or install Python.
- `No module named yaml`: run `pip install -r requirements.txt`.
- No DBL rows: the IP may not have a PTR record, or no derived domain is listed.
