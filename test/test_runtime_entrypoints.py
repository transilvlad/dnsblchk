import os
import subprocess
import sys
from pathlib import Path

import pytest

from main import _parse_args


def test_parse_args_accepts_positional_config():
    assert _parse_args(["config/config-local.yaml"]) == "config/config-local.yaml"


def test_parse_args_accepts_config_option():
    assert _parse_args(["--config", "config/custom.yaml"]) == "config/custom.yaml"


def test_parse_args_rejects_conflicting_config_paths():
    with pytest.raises(SystemExit):
        _parse_args(["config/one.yaml", "--config", "config/two.yaml"])


def test_installed_console_script_can_show_help_without_default_config(tmp_path):
    install_dir = tmp_path / "install"

    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-build-isolation",
            "--target",
            str(install_dir),
            ".",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert install.returncode == 0, install.stderr

    console_script = install_dir / "bin" / "dnsblchk"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(install_dir)
    result = subprocess.run(
        [str(console_script), "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "DNS Block List Checker" in result.stdout


def test_installed_console_script_runs_with_explicit_config(tmp_path):
    install_dir = tmp_path / "install"
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "logs").mkdir()
    (app_dir / "ips.txt").write_text("192.0.2.10\n", encoding="utf-8")
    (app_dir / "rbls.txt").write_text("", encoding="utf-8")
    (app_dir / "dbls.txt").write_text("", encoding="utf-8")
    config_file = app_dir / "config.yaml"
    config_file.write_text(
        """
run_once: true
sleep_hours: 3
keep_last_reports: 1
rbls_file: "rbls.txt"
dbls_file: "dbls.txt"
ips_file: "ips.txt"
report_dir: "logs"
nameservers:
  - "208.67.222.222"
threading:
  enabled: false
  thread_count: 1
email:
  enabled: false
webhooks:
  enabled: false
api_update:
  enabled: false
logging:
  level: "ERROR"
  console_print: false
  log_dir: "logs"
  log_file: "dnsblchk.log"
  clear_log_on_start: true
  run_log_dir: "logs/runs"
  keep_last_runs: 1
""",
        encoding="utf-8",
    )

    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-build-isolation",
            "--target",
            str(install_dir),
            ".",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert install.returncode == 0, install.stderr

    console_script = install_dir / "bin" / "dnsblchk"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(install_dir)
    result = subprocess.run(
        [str(console_script), str(config_file)],
        cwd=app_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr


def test_systemd_service_uses_installed_console_script():
    service = Path("dnsblchk.service").read_text(encoding="utf-8")

    assert "ExecStart=/usr/bin/dnsblchk /etc/dnsblchk/config.yaml" in service
    assert "/opt/dnsblchk/main.py" not in service


def test_debian_install_template_places_config_under_etc():
    install_template = Path("packaging/debian/install").read_text(encoding="utf-8")

    assert "config/config.yaml etc/dnsblchk/" in install_template
    assert "opt/dnsblchk" not in install_template


def test_dockerfile_uses_docker_config():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    docker_config = Path("config/config-docker.yaml").read_text(encoding="utf-8")

    assert 'CMD ["config/config-docker.yaml"]' in dockerfile
    assert 'rbls_file: "config/rbls.txt"' in docker_config
    assert 'log_dir: "logs/"' in docker_config
