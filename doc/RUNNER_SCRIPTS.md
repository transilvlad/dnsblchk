# Runner Scripts

The repository includes three local runner scripts:

| Script | Platform | Best for |
| --- | --- | --- |
| `run.sh` | Linux, macOS, WSL | Unix-like shells |
| `run.bat` | Windows Command Prompt | Native Windows usage |
| `run.py` | Any platform | Cross-platform behavior |

Each runner:

- Detects Python 3.14 or newer.
- Prefers active virtual environments and local `.venv` directories.
- Validates `main.py` and the selected config file.
- Runs `main.py` with the selected config path.

## Quick Reference

```bash
./run.sh
./run.sh --config config/config-local.yaml
./run.sh --extended

python run.py
python run.py --config config/custom.yaml
python run.py --extended
```

Windows:

```cmd
run.bat
run.bat --config config\config-local.yaml
run.bat --extended
```

## Config Selection

Default:

```text
config/config-local.yaml
```

Extended:

```text
config/config-local-extended.yaml
```

Custom:

```bash
python run.py --config config/custom.yaml
```

## Troubleshooting

- Missing config: restore `config/config-local.yaml` or pass `--config`.
- Missing dependencies: run `pip install -r requirements.txt`.
- Wrong Python: activate your virtual environment before running the script.
