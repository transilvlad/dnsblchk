from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

import main as app_main


class TestMainApplication:
    def test_init_loads_explicit_config(self):
        with patch("main.config") as mock_config:
            app = app_main.MainApplication("config/custom.yaml")

        mock_config.load.assert_called_once_with("config/custom.yaml")
        assert app.logger is None
        assert app.rbls is None
        assert app.dbls is None
        assert app.ips is None

    def test_setup_logger_truncates_configured_log_file(self, tmp_path):
        log_file = tmp_path / "dnsblchk.log"
        log_file.write_text("old log\n", encoding="utf-8")

        with patch("main.config") as mock_config, patch("main.Logger") as mock_logger:
            mock_config.get_run_log_dir.return_value = None
            mock_config.log_file = log_file
            mock_config.log_dir = tmp_path
            mock_config.get_log_level.return_value = app_main.LogConfig().level
            mock_config.get_console_print.return_value = False
            mock_config.get_keep_last_runs.return_value = 3
            mock_config.get_clear_log_on_start.return_value = True

            app = app_main.MainApplication()
            app._setup_logger()

        assert log_file.read_text(encoding="utf-8") == ""
        mock_logger.assert_called_once()

    def test_setup_logger_reports_truncate_failure(self, tmp_path):
        with patch("main.config") as mock_config, patch("main.Logger"), patch("builtins.open", mock_open()) as mocked_open, patch("builtins.print") as mocked_print:
            mocked_open.side_effect = OSError("denied")
            mock_config.get_run_log_dir.return_value = None
            mock_config.log_file = tmp_path / "dnsblchk.log"
            mock_config.log_dir = tmp_path
            mock_config.get_log_level.return_value = app_main.LogConfig().level
            mock_config.get_console_print.return_value = False
            mock_config.get_keep_last_runs.return_value = 3
            mock_config.get_clear_log_on_start.return_value = True

            app = app_main.MainApplication()
            app._setup_logger()

        assert "Failed to clear log file on start" in mocked_print.call_args.args[0]

    def test_setup_signal_handlers_registers_handlers(self):
        logger = MagicMock()
        signal_handler = MagicMock()

        with patch("main.SignalHandler", return_value=signal_handler):
            app = app_main.MainApplication()
            app.logger = logger
            app._setup_signal_handlers()

        signal_handler.setup_signal_handlers.assert_called_once()
        logger.log_debug.assert_called_once()

    def test_setup_clients_and_checkers_with_api_enabled(self):
        logger = MagicMock()
        with patch("main.config") as mock_config, patch("main.MailClient") as mock_mail, patch("main.WebhookClient") as mock_webhook, patch("main.ApiClient") as mock_api, patch("main.RBLCheck") as mock_rbl:
            mock_config.get_smtp_host.return_value = "localhost"
            mock_config.get_smtp_port.return_value = 25
            mock_config.get_smtp_user.return_value = ""
            mock_config.get_smtp_password.return_value = ""
            mock_config.get_smtp_use_tls.return_value = False
            mock_config.get_smtp_use_ssl.return_value = False
            mock_config.get_webhook_urls.return_value = []
            mock_config.get_webhook_timeout.return_value = 10
            mock_config.is_api_update_enabled.return_value = True
            mock_config.get_api_update_url.return_value = "https://api.example.com/ips"
            mock_config.get_api_update_auth_type.return_value = "bearer"
            mock_config.get_api_update_username.return_value = ""
            mock_config.get_api_update_password.return_value = ""
            mock_config.get_api_update_bearer_token.return_value = "token"
            mock_config.get_api_update_timeout.return_value = 5
            mock_config.get_nameservers.return_value = ["208.67.222.222"]
            mock_config.get_nameservers_confirm.return_value = []
            mock_config.get_slack_bot_token.return_value = ""
            mock_config.get_slack_channel_id.return_value = ""

            app = app_main.MainApplication()
            app.logger = logger
            app._setup_clients_and_checkers()

        mock_mail.assert_called_once()
        mock_webhook.assert_called_once()
        mock_api.assert_called_once()
        mock_rbl.assert_called_once_with(
            nameservers=["208.67.222.222"],
            nameservers_confirm=[],
            logger=logger,
        )
        assert app.api_client == mock_api.return_value

    def test_load_configuration_handles_missing_dbl_file(self, tmp_path):
        rbls_file = tmp_path / "rbls.txt"
        ips_file = tmp_path / "ips.txt"
        rbls_file.write_text("rbl.example.com\n", encoding="utf-8")
        ips_file.write_text("192.0.2.10\n", encoding="utf-8")

        with patch("main.config") as mock_config:
            mock_config.get_rbls_file.return_value = rbls_file
            mock_config.get_dbls_file.return_value = tmp_path / "missing-dbls.txt"
            mock_config.ips_file = ips_file
            app = app_main.MainApplication()
            app.logger = MagicMock()
            app._load_configuration()

        assert app.rbls == [["rbl.example.com"]]
        assert app.dbls == []
        assert app.ips == [["192.0.2.10"]]

    def test_update_ips_from_api_disabled(self):
        with patch("main.config") as mock_config:
            mock_config.is_api_update_enabled.return_value = False
            app = app_main.MainApplication()
            app.logger = MagicMock()
            app._update_ips_from_api()

        app.logger.log_debug.assert_called_with("API update is disabled, skipping IP update from API")

    def test_update_ips_from_api_enabled_without_client(self):
        with patch("main.config") as mock_config:
            mock_config.is_api_update_enabled.return_value = True
            app = app_main.MainApplication()
            app.logger = MagicMock()
            app._update_ips_from_api()

        app.logger.log_warning.assert_called_once()

    def test_update_ips_from_api_success_and_failure(self):
        with patch("main.config") as mock_config:
            mock_config.is_api_update_enabled.return_value = True
            app = app_main.MainApplication()
            app.logger = MagicMock()
            app.api_client = MagicMock()
            app.api_client.fetch_ips.return_value = (True, ["192.0.2.10", "198.51.100.10"], None)
            app._update_ips_from_api()
            assert app.ips == [["192.0.2.10"], ["198.51.100.10"]]

            app.api_client.fetch_ips.return_value = (False, [], "boom")
            app._update_ips_from_api()

        app.logger.log_warning.assert_called_once()

    def test_run_checks_updates_ips_and_delegates(self):
        app = app_main.MainApplication()
        app.rbls = [["rbl.example.com"]]
        app.dbls = [["dbl.example.com"]]
        app.ips = [["192.0.2.10"]]
        app.check_handler = MagicMock()

        with patch.object(app, "_update_ips_from_api") as update_mock:
            app._run_checks()

        update_mock.assert_called_once()
        app.check_handler.run.assert_called_once_with(app.rbls, app.dbls, app.ips)

    def test_sleep_with_shutdown_check_stops_early(self):
        app = app_main.MainApplication()
        app.signal_handler = MagicMock()
        app.signal_handler.is_shutdown_requested = True

        with patch("main.time.sleep") as sleep_mock:
            app._sleep_with_shutdown_check(30)

        sleep_mock.assert_not_called()

    def test_run_once_successful_cycle(self):
        with patch("main.config") as mock_config:
            mock_config.run_once = True
            app = app_main.MainApplication()
            app.logger = MagicMock()
            app.signal_handler = MagicMock()
            app.signal_handler.is_shutdown_requested = False
            app._initialize = MagicMock()
            app._run_checks = MagicMock()

            app.run()

        app.logger.start_run.assert_called_once()
        app.logger.end_run.assert_called_once()
        app._run_checks.assert_called_once()
        app.logger.log_info.assert_called_with("DNSblChk service shutdown complete.")

    def test_run_once_logs_cycle_failure(self):
        with patch("main.config") as mock_config:
            mock_config.run_once = True
            app = app_main.MainApplication()
            app.logger = MagicMock()
            app.signal_handler = MagicMock()
            app.signal_handler.is_shutdown_requested = False
            app._initialize = MagicMock()
            app._run_checks = MagicMock(side_effect=RuntimeError("cycle failed"))

            app.run()

        app.logger.log_error.assert_called_with("Check cycle failed: cycle failed")


def test_main_load_failure_prints_target_to_stderr(capsys):
    with patch("main.config") as mock_config:
        mock_config.load.side_effect = FileNotFoundError("missing")

        with pytest.raises(FileNotFoundError):
            app_main.main(["config/missing.yaml"])

    assert "Failed to load configuration from config/missing.yaml" in capsys.readouterr().err


def test_main_runs_application():
    with patch("main.config") as mock_config, patch("main.MainApplication") as mock_app:
        app_main.main(["config/config-local.yaml"])

    mock_config.load.assert_called_once_with("config/config-local.yaml")
    mock_app.return_value.run.assert_called_once()
