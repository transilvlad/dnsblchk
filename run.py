#!/usr/bin/env python3
"""Cross-platform local runner for dnsblchk."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"

    @staticmethod
    def disable_on_legacy_windows() -> None:
        if sys.platform != "win32":
            return
        import platform
        try:
            release_major = int(platform.release().split(".", 1)[0])
        except ValueError:
            release_major = 0
        if release_major < 10:
            for attr in ("RESET", "RED", "GREEN", "YELLOW", "BLUE"):
                setattr(Colors, attr, "")


class Log:
    @staticmethod
    def info(message: str) -> None:
        print(f"{Colors.GREEN}[INFO]{Colors.RESET} {message}")

    @staticmethod
    def warn(message: str) -> None:
        print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {message}")

    @staticmethod
    def error(message: str) -> None:
        print(f"{Colors.RED}[ERROR]{Colors.RESET} {message}", file=sys.stderr)

    @staticmethod
    def section(message: str) -> None:
        print(f"\n{Colors.BLUE}>>> {message}{Colors.RESET}")


class PythonFinder:
    @staticmethod
    def find() -> Optional[str]:
        for candidate in PythonFinder._candidates():
            if PythonFinder._is_valid(candidate):
                return candidate
        return None

    @staticmethod
    def _candidates() -> list[str]:
        candidates = ["python3", "python"]

        virtual_env = os.environ.get("VIRTUAL_ENV")
        if virtual_env:
            candidates.extend([
                os.path.join(virtual_env, "bin", "python"),
                os.path.join(virtual_env, "bin", "python3"),
                os.path.join(virtual_env, "Scripts", "python.exe"),
                os.path.join(virtual_env, "Scripts", "python"),
            ])

        candidates.extend([
            ".venv/bin/python",
            ".venv/bin/python3",
            ".venv/Scripts/python.exe",
            ".venv/Scripts/python",
            "venv/bin/python",
            "venv/bin/python3",
            "venv/Scripts/python.exe",
            "venv/Scripts/python",
        ])

        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            candidates.extend([
                os.path.join(conda_prefix, "bin", "python"),
                os.path.join(conda_prefix, "Scripts", "python.exe"),
            ])

        return candidates

    @staticmethod
    def _is_valid(python_exe: str) -> bool:
        try:
            result = subprocess.run(
                [python_exe, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False
            version = (result.stdout or result.stderr).strip().split()[1]
            major, minor, *_ = version.split(".")
            return int(major) > 3 or (int(major) == 3 and int(minor) >= 14)
        except (FileNotFoundError, IndexError, subprocess.TimeoutExpired, ValueError):
            return False


class Environment:
    @staticmethod
    def name() -> str:
        if os.environ.get("VIRTUAL_ENV"):
            return f"venv ({os.environ['VIRTUAL_ENV']})"
        if os.environ.get("CONDA_DEFAULT_ENV"):
            return f"conda ({os.environ['CONDA_DEFAULT_ENV']})"
        if Path(".venv").exists():
            return "local .venv"
        if Path("venv").exists():
            return "local venv"
        return "system Python"

    @staticmethod
    def os_name() -> str:
        if sys.platform == "win32":
            return "Windows"
        if sys.platform == "darwin":
            return "macOS"
        return "Linux"


class Runner:
    def __init__(self) -> None:
        self.root = Path(__file__).parent.absolute()
        self.main_py = self.root / "main.py"
        self.default_config = self.root / "config" / "config-local.yaml"
        self.extended_config = self.root / "config" / "config-local-extended.yaml"

    def config_path(self, extended: bool, custom_config: Optional[str]) -> Path:
        if custom_config:
            path = Path(custom_config)
            return path if path.is_absolute() else self.root / path
        return self.extended_config if extended else self.default_config

    def validate(self, config_file: Path) -> bool:
        if not self.main_py.exists():
            Log.error(f"main.py not found: {self.main_py}")
            return False
        if not config_file.exists():
            Log.error(f"Config file not found: {config_file}")
            Log.error("Restore config/config-local.yaml or pass --config PATH.")
            return False
        return True

    def run(self, args: argparse.Namespace) -> int:
        Log.section("Starting dnsblchk Local Runner")
        Log.info(f"Operating System: {Environment.os_name()}")
        Log.info(f"Python Environment: {Environment.name()}")

        config_file = self.config_path(args.extended, args.config)
        Log.section("Validating configuration")
        if not self.validate(config_file):
            return 1
        Log.info("Configuration file validated")

        Log.section("Locating Python")
        python_exe = PythonFinder.find()
        if not python_exe:
            Log.error("Python 3.14+ not found in PATH or virtual environments")
            return 1
        Log.info(f"Found Python: {python_exe}")

        Log.section("Ready to start dnsblchk")
        print(f"  Python:      {python_exe}")
        print(f"  Config file: {config_file}")
        print(f"  Main script: {self.main_py}")

        if args.verbose:
            Log.info("Verbose runner output enabled")

        try:
            os.chdir(self.root)
            return subprocess.run([python_exe, str(self.main_py), str(config_file)]).returncode
        except KeyboardInterrupt:
            print()
            Log.warn("Interrupted by user")
            return 130


def main() -> int:
    Colors.disable_on_legacy_windows()
    parser = argparse.ArgumentParser(description="DNS Block List Checker local runner")
    parser.add_argument("-e", "--extended", action="store_true", help="Use config/config-local-extended.yaml")
    parser.add_argument("-c", "--config", help="Use a custom config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose runner output")
    args = parser.parse_args()
    return Runner().run(args)


if __name__ == "__main__":
    sys.exit(main())
