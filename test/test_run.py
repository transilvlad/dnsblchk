import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import run


class TestColors:
    def test_disable_on_non_windows_does_nothing(self):
        with patch("run.sys.platform", "linux"):
            run.Colors.disable_on_legacy_windows()

        assert run.Colors.RESET == "\033[0m"

    def test_disable_on_legacy_windows_clears_color_codes(self):
        original = {name: getattr(run.Colors, name) for name in ("RESET", "RED", "GREEN", "YELLOW", "BLUE")}
        try:
            with patch("run.sys.platform", "win32"), patch("platform.release", return_value="7"):
                run.Colors.disable_on_legacy_windows()

            assert all(getattr(run.Colors, name) == "" for name in original)
        finally:
            for name, value in original.items():
                setattr(run.Colors, name, value)


class TestPythonFinder:
    def test_candidates_include_virtualenv_and_conda_paths(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_ENV", "/tmp/venv")
        monkeypatch.setenv("CONDA_PREFIX", "/tmp/conda")

        candidates = run.PythonFinder._candidates()

        assert "/tmp/venv/bin/python" in candidates
        assert "/tmp/venv/Scripts/python.exe" in candidates
        assert "/tmp/conda/bin/python" in candidates

    @pytest.mark.parametrize(
        ("stdout", "returncode", "expected"),
        [
            ("Python 3.10.0\n", 0, True),
            ("Python 3.9.18\n", 0, False),
            ("", 1, False),
        ],
    )
    def test_is_valid_checks_version_and_return_code(self, stdout, returncode, expected):
        completed = MagicMock(returncode=returncode, stdout=stdout, stderr="")

        with patch("run.subprocess.run", return_value=completed):
            assert run.PythonFinder._is_valid("python") is expected

    def test_is_valid_handles_process_errors(self):
        with patch("run.subprocess.run", side_effect=FileNotFoundError):
            assert run.PythonFinder._is_valid("missing-python") is False

    def test_find_returns_first_valid_candidate(self):
        with patch.object(run.PythonFinder, "_candidates", return_value=["bad", "good"]), patch.object(run.PythonFinder, "_is_valid", side_effect=[False, True]):
            assert run.PythonFinder.find() == "good"

    def test_find_returns_none_when_no_candidate_valid(self):
        with patch.object(run.PythonFinder, "_candidates", return_value=["bad"]), patch.object(run.PythonFinder, "_is_valid", return_value=False):
            assert run.PythonFinder.find() is None


class TestEnvironment:
    def test_name_prefers_virtualenv(self, monkeypatch):
        monkeypatch.setenv("VIRTUAL_ENV", "/tmp/venv")

        assert run.Environment.name() == "venv (/tmp/venv)"

    def test_name_detects_conda(self, monkeypatch):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.setenv("CONDA_DEFAULT_ENV", "dnsblchk")

        assert run.Environment.name() == "conda (dnsblchk)"

    def test_name_detects_local_venv(self, tmp_path, monkeypatch):
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)
        monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".venv").mkdir()

        assert run.Environment.name() == "local .venv"

    @pytest.mark.parametrize(
        ("platform", "expected"),
        [("win32", "Windows"), ("darwin", "macOS"), ("linux", "Linux")],
    )
    def test_os_name(self, platform, expected):
        with patch("run.sys.platform", platform):
            assert run.Environment.os_name() == expected


class TestRunner:
    def test_config_path_selection(self, tmp_path):
        runner = run.Runner()
        runner.root = tmp_path
        runner.default_config = tmp_path / "config" / "config-local.yaml"
        runner.extended_config = tmp_path / "config" / "config-local-extended.yaml"

        assert runner.config_path(False, None) == runner.default_config
        assert runner.config_path(True, None) == runner.extended_config
        assert runner.config_path(False, "custom.yaml") == tmp_path / "custom.yaml"
        assert runner.config_path(False, str(tmp_path / "absolute.yaml")) == tmp_path / "absolute.yaml"

    def test_validate_checks_main_and_config(self, tmp_path):
        runner = run.Runner()
        runner.main_py = tmp_path / "main.py"
        config_file = tmp_path / "config.yaml"

        assert runner.validate(config_file) is False

        runner.main_py.write_text("print('ok')\n", encoding="utf-8")
        assert runner.validate(config_file) is False

        config_file.write_text("run_once: true\n", encoding="utf-8")
        assert runner.validate(config_file) is True

    def test_run_returns_one_when_validation_fails(self):
        runner = run.Runner()
        args = argparse.Namespace(extended=False, config=None, verbose=False)

        with patch.object(runner, "validate", return_value=False):
            assert runner.run(args) == 1

    def test_run_returns_one_when_python_missing(self):
        runner = run.Runner()
        args = argparse.Namespace(extended=False, config=None, verbose=False)

        with patch.object(runner, "validate", return_value=True), patch.object(run.PythonFinder, "find", return_value=None):
            assert runner.run(args) == 1

    def test_run_executes_main_script_and_returns_subprocess_code(self, tmp_path):
        runner = run.Runner()
        runner.root = tmp_path
        runner.main_py = tmp_path / "main.py"
        runner.default_config = tmp_path / "config.yaml"
        args = argparse.Namespace(extended=False, config=None, verbose=True)
        completed = MagicMock(returncode=7)

        with patch.object(runner, "validate", return_value=True), patch.object(run.PythonFinder, "find", return_value="python3"), patch("run.subprocess.run", return_value=completed) as subprocess_run, patch("run.os.chdir") as chdir_mock:
            assert runner.run(args) == 7

        chdir_mock.assert_called_once_with(tmp_path)
        subprocess_run.assert_called_once_with(["python3", str(runner.main_py), str(runner.default_config)])

    def test_run_returns_130_on_keyboard_interrupt(self, tmp_path):
        runner = run.Runner()
        runner.root = tmp_path
        runner.main_py = tmp_path / "main.py"
        runner.default_config = tmp_path / "config.yaml"
        args = argparse.Namespace(extended=False, config=None, verbose=False)

        with patch.object(runner, "validate", return_value=True), patch.object(run.PythonFinder, "find", return_value="python3"), patch("run.subprocess.run", side_effect=KeyboardInterrupt), patch("run.os.chdir"):
            assert runner.run(args) == 130


def test_main_parses_args_and_runs_runner():
    with patch("run.sys.argv", ["run.py"]), patch("run.Colors.disable_on_legacy_windows") as colors_mock, patch("run.Runner") as runner_class:
        runner_class.return_value.run.return_value = 0

        assert run.main() == 0

    colors_mock.assert_called_once()
    runner_class.return_value.run.assert_called_once()
