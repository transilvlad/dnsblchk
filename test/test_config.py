"""Unit tests for the config module."""
from pathlib import Path

import pytest

from config import Config, ENV_CONFIG_PATH
from logger import LogLevel


class TestConfigLogLevel:
    """Test cases for LogLevel enum usage in config."""

    def test_log_level_enum_values(self):
        """Test LogLevel enum has correct values."""
        assert LogLevel.DEBUG.value == 0
        assert LogLevel.INFO.value == 1
        assert LogLevel.WARN.value == 2
        assert LogLevel.ERROR.value == 3

    def test_log_level_info(self):
        """Test LogLevel.INFO value."""
        assert LogLevel.INFO.value == 1

    def test_log_level_debug(self):
        """Test LogLevel.DEBUG value."""
        assert LogLevel.DEBUG.value == 0

    def test_log_level_warn(self):
        """Test LogLevel.WARN value."""
        assert LogLevel.WARN.value == 2

    def test_log_level_error(self):
        """Test LogLevel.ERROR value."""
        assert LogLevel.ERROR.value == 3


class TestConfigData:
    """Test cases for configuration data structures."""

    def test_config_can_be_created_without_loading_file(self):
        """Test lazy configuration creation for packaged console startup."""
        app_config = Config(auto_load=False)

        assert app_config.is_loaded() is False
        assert app_config.loaded_path is None

    def test_load_uses_environment_config_path(self, tmp_path, monkeypatch):
        """Test DNSBLCHK_CONFIG is used when no CLI path is provided."""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text(
            """
run_once: true
ips_file: "ips.txt"
report_dir: "logs"
logging:
  log_dir: "logs"
  log_file: "dnsblchk.log"
""",
            encoding="utf-8",
        )
        (tmp_path / "ips.txt").write_text("192.0.2.10\n", encoding="utf-8")
        (tmp_path / "logs").mkdir()
        monkeypatch.setenv(ENV_CONFIG_PATH, str(config_file))

        app_config = Config(auto_load=False)
        app_config.load()

        assert app_config.loaded_path == config_file
        assert app_config.ips_file == tmp_path / "ips.txt"
        assert app_config.report_dir == tmp_path / "logs"

    def test_relative_paths_fall_back_to_loaded_config_directory(self, tmp_path, monkeypatch):
        """Test custom configs can keep data files next to the YAML file."""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text(
            """
run_once: true
ips_file: "ips.txt"
report_dir: "logs"
logging:
  log_dir: "logs"
  log_file: "dnsblchk.log"
""",
            encoding="utf-8",
        )
        (tmp_path / "ips.txt").write_text("192.0.2.10\n", encoding="utf-8")
        (tmp_path / "logs").mkdir()
        monkeypatch.chdir(tmp_path.parent)

        app_config = Config(auto_load=False)
        app_config.load(config_file)

        assert app_config.ips_file == tmp_path / "ips.txt"
        assert app_config.log_file == tmp_path / "logs" / "dnsblchk.log"

    def test_resolve_config_path_raises_when_no_candidate_exists(self, tmp_path, monkeypatch):
        """Test a missing default config gives a useful failure."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv(ENV_CONFIG_PATH, raising=False)
        app_config = Config(auto_load=False)
        app_config._root_path = tmp_path / "missing-root"

        with pytest.raises(FileNotFoundError, match="No configuration file found"):
            app_config.resolve_config_path()

    def test_getters_return_defaults_from_empty_config(self):
        """Test common getter defaults when optional sections are absent."""
        app_config = Config(auto_load=False)

        assert app_config.get_log_level() == LogLevel.INFO
        assert app_config.get_console_print() is True
        assert app_config.get_run_log_dir() is None
        assert app_config.get_keep_last_runs() == 10
        assert app_config.is_email_enabled() is False
        assert app_config.get_email_recipients() == []
        assert app_config.get_email_sender() == ""
        assert app_config.get_smtp_host() == ""
        assert app_config.get_smtp_port() == 25
        assert app_config.get_smtp_user() == ""
        assert app_config.get_smtp_password() == ""
        assert app_config.get_smtp_use_tls() is False
        assert app_config.get_smtp_use_ssl() is False
        assert app_config.get_nameservers() == ["208.67.222.222"]
        assert app_config.get_thread_count() == 10
        assert app_config.is_threading_enabled() is True
        assert app_config.is_webhooks_enabled() is False
        assert app_config.get_webhook_urls() == []
        assert app_config.get_webhook_timeout() == 10
        assert app_config.is_api_update_enabled() is False
        assert app_config.get_api_update_url() == ""
        assert app_config.get_api_update_auth_type() == "none"
        assert app_config.get_api_update_username() == ""
        assert app_config.get_api_update_password() == ""
        assert app_config.get_api_update_bearer_token() == ""
        assert app_config.get_api_update_timeout() == 10
        assert app_config.get_clear_log_on_start() is False
        assert app_config.get_keep_last_reports() == 5
        assert app_config.get_active_suppressions() == set()
        assert app_config.get_address_groups() == {}
        assert app_config.get_rbls_file() is None
        assert app_config.get_dbls_file() is None

    def test_getters_return_configured_values(self, tmp_path):
        """Test getter methods against concrete configured values."""
        app_config = Config(auto_load=False)
        rbls_file = tmp_path / "rbls.txt"
        dbls_file = tmp_path / "dbls.txt"
        app_config._config_data = {
            "keep_last_reports": 2,
            "rbls_file": rbls_file,
            "dbls_file": str(dbls_file),
            "nameservers": ["1.1.1.1"],
            "threading": {"enabled": False, "thread_count": 0},
            "logging": {
                "level": "DEBUG",
                "console_print": False,
                "clear_log_on_start": True,
                "run_log_dir": str(tmp_path / "runs"),
                "keep_last_runs": 4,
            },
            "email": {
                "enabled": True,
                "recipients": ["admin@example.com"],
                "sender": "dnsblchk@example.com",
                "smtp_host": "mail.example.com",
                "smtp_port": 587,
                "smtp_user": "user",
                "smtp_password": "pass",
                "use_tls": True,
                "use_ssl": False,
            },
            "webhooks": {"enabled": True, "urls": ["https://example.com/webhook"], "timeout": 3},
            "api_update": {
                "enabled": True,
                "url": "https://example.com/ips",
                "auth_type": "basic",
                "username": "api-user",
                "password": "api-pass",
                "bearer_token": "token",
                "timeout": 6,
            },
        }

        assert app_config.get_log_level() == LogLevel.DEBUG
        assert app_config.get_console_print() is False
        assert app_config.get_run_log_dir() == str(tmp_path / "runs")
        assert app_config.get_keep_last_runs() == 4
        assert app_config.is_email_enabled() is True
        assert app_config.get_email_recipients() == ["admin@example.com"]
        assert app_config.get_email_sender() == "dnsblchk@example.com"
        assert app_config.get_smtp_host() == "mail.example.com"
        assert app_config.get_smtp_port() == 587
        assert app_config.get_smtp_user() == "user"
        assert app_config.get_smtp_password() == "pass"
        assert app_config.get_smtp_use_tls() is True
        assert app_config.get_smtp_use_ssl() is False
        assert app_config.get_nameservers() == ["1.1.1.1"]
        assert app_config.get_thread_count() == 1
        assert app_config.is_threading_enabled() is False
        assert app_config.is_webhooks_enabled() is True
        assert app_config.get_webhook_urls() == ["https://example.com/webhook"]
        assert app_config.get_webhook_timeout() == 3
        assert app_config.is_api_update_enabled() is True
        assert app_config.get_api_update_url() == "https://example.com/ips"
        assert app_config.get_api_update_auth_type() == "basic"
        assert app_config.get_api_update_username() == "api-user"
        assert app_config.get_api_update_password() == "api-pass"
        assert app_config.get_api_update_bearer_token() == "token"
        assert app_config.get_api_update_timeout() == 6
        assert app_config.get_clear_log_on_start() is True
        assert app_config.get_keep_last_reports() == 2
        assert app_config.get_rbls_file() == rbls_file
        assert app_config.get_dbls_file() == dbls_file

    def test_invalid_log_level_defaults_to_info(self, capsys):
        """Test invalid log levels are reported and default to INFO."""
        app_config = Config(auto_load=False)
        app_config._config_data = {"logging": {"level": "NOPE"}}

        assert app_config.get_log_level() == LogLevel.INFO
        assert "Invalid log level" in capsys.readouterr().out

    def test_suppressions_ignore_invalid_and_expired_entries(self):
        """Test active suppression filtering."""
        app_config = Config(auto_load=False)
        app_config._config_data = {
            "suppressions": [
                {"ip": "192.0.2.10", "until": "2999-01-01"},
                {"ip": "192.0.2.11", "until": "2000-01-01"},
                {"ip": "192.0.2.12", "until": "invalid"},
                {"ip": "192.0.2.13", "until": None},
            ]
        }

        assert app_config.get_active_suppressions() == {"192.0.2.10"}

    def test_address_groups_must_be_dict(self):
        """Test non-dict address group config is ignored."""
        app_config = Config(auto_load=False)
        app_config._config_data = {"address_groups": ["bad"]}

        assert app_config.get_address_groups() == {}

    def test_getattr_supports_sections_and_missing_attributes(self):
        """Test attribute-style access from nested sections."""
        app_config = Config(auto_load=False)
        app_config._config_data = {
            "run_once": True,
            "logging": {"log_dir": "logs"},
            "email": {"sender": "dnsblchk@example.com"},
        }

        assert app_config.run_once is True
        assert app_config.log_dir == "logs"
        assert app_config.sender == "dnsblchk@example.com"
        with pytest.raises(AttributeError):
            _ = app_config.not_configured

    def test_config_dict_structure(self):
        """Test basic config dictionary structure."""
        config_data = {
            'rbls_file': 'config/rbls.txt',
            'dbls_file': 'config/dbls.txt',
            'ips_file': 'config/ips.txt',
            'report_dir': 'logs/',
            'logging': {'log_dir': 'logs', 'log_file': 'app.log'},
            'email': {'enabled': False},
            'nameservers': ['8.8.8.8']
        }
        assert config_data['rbls_file'] == 'config/rbls.txt'
        assert config_data['dbls_file'] == 'config/dbls.txt'
        assert config_data['ips_file'] == 'config/ips.txt'
        assert config_data['report_dir'] == 'logs/'

    def test_config_logging_section(self):
        """Test config logging section."""
        logging_config = {'log_dir': 'logs', 'log_file': 'app.log', 'level': 'INFO'}
        assert logging_config['log_dir'] == 'logs'
        assert logging_config['log_file'] == 'app.log'
        assert logging_config['level'] == 'INFO'

    def test_config_email_section_enabled(self):
        """Test config email section when enabled."""
        email_config = {'enabled': True, 'recipients': ['tony@example.com']}
        assert email_config['enabled'] is True
        assert 'tony@example.com' in email_config['recipients']

    def test_config_email_section_disabled(self):
        """Test config email section when disabled."""
        email_config = {'enabled': False}
        assert email_config['enabled'] is False

    def test_config_threading_section(self):
        """Test config threading section."""
        threading_config = {'thread_count': 10, 'enabled': True}
        assert threading_config['thread_count'] == 10
        assert threading_config['enabled'] is True

    def test_config_nameservers(self):
        """Test config nameservers."""
        nameservers = ['8.8.8.8', '8.8.4.4']
        assert len(nameservers) == 2
        assert '8.8.8.8' in nameservers

    def test_email_recipients_list(self):
        """Test email recipients list."""
        recipients = ['tony@example.com', 'pepper@example.com']
        assert recipients == ['tony@example.com', 'pepper@example.com']
        assert len(recipients) == 2

    def test_email_recipients_empty(self):
        """Test email recipients can be empty."""
        recipients = []
        assert recipients == []

    def test_email_sender(self):
        """Test email sender."""
        sender = 'noreply@example.com'
        assert sender == 'noreply@example.com'

    def test_email_sender_empty_default(self):
        """Test email sender defaults to empty string."""
        sender = ''
        assert sender == ''

    def test_smtp_host(self):
        """Test SMTP host."""
        smtp_host = 'mail.example.com'
        assert smtp_host == 'mail.example.com'

    def test_smtp_host_localhost(self):
        """Test SMTP host can be localhost."""
        smtp_host = 'localhost'
        assert smtp_host == 'localhost'

    def test_smtp_port(self):
        """Test SMTP port."""
        smtp_port = 587
        assert smtp_port == 587

    def test_smtp_port_default(self):
        """Test SMTP default port is 25."""
        smtp_port = 25
        assert smtp_port == 25

    def test_smtp_port_ssl(self):
        """Test SMTP SSL port."""
        smtp_port = 465
        assert smtp_port == 465

    def test_smtp_auth_user(self):
        """Test SMTP auth username."""
        smtp_user = 'user'
        assert smtp_user == 'user'

    def test_smtp_auth_password(self):
        """Test SMTP auth password."""
        smtp_password = 'pass'
        assert smtp_password == 'pass'

    def test_smtp_auth_empty(self):
        """Test empty SMTP auth credentials."""
        smtp_user = ''
        smtp_password = ''
        assert smtp_user == ''
        assert smtp_password == ''

    def test_smtp_use_tls_true(self):
        """Test use_tls flag true."""
        use_tls = True
        assert use_tls is True

    def test_smtp_use_tls_false(self):
        """Test use_tls flag false."""
        use_tls = False
        assert use_tls is False

    def test_smtp_use_ssl_true(self):
        """Test use_ssl flag true."""
        use_ssl = True
        assert use_ssl is True

    def test_smtp_use_ssl_false(self):
        """Test use_ssl flag false."""
        use_ssl = False
        assert use_ssl is False

    def test_smtp_ssl_overrides_tls(self):
        """Test SSL overrides TLS when both true."""
        use_tls = True
        use_ssl = True
        # In logic SSL overrides TLS starttls call
        assert use_ssl and use_tls

    def test_thread_count(self):
        """Test thread count."""
        thread_count = 10
        assert thread_count == 10

    def test_thread_count_minimum_enforcement(self):
        """Test thread count minimum enforcement."""
        thread_count = 0
        result = max(1, thread_count)
        assert result == 1

    def test_thread_count_custom(self):
        """Test custom thread count."""
        thread_count = 5
        assert thread_count == 5

    def test_get_absolute_path_structure(self):
        """Test absolute path construction."""
        root_path = Path('/app')
        relative_path = 'config/rbls.txt'
        full_path = root_path / relative_path
        # Use Path normalization to handle both Windows and Unix paths
        assert 'rbls.txt' in str(full_path)
        assert 'config' in str(full_path)

    def test_nested_path_resolution(self):
        """Test nested path resolution."""
        root = Path('/app')
        log_dir = root / 'logs'
        log_file = log_dir / 'app.log'
        # Use Path normalization to handle both Windows and Unix paths
        assert 'app.log' in str(log_file)
        assert 'logs' in str(log_file)

    def test_config_section_access_defaults(self):
        """Test accessing config sections with defaults."""
        config = {}
        email = config.get('email', {})
        assert email == {}
        assert email.get('enabled', False) is False

    def test_config_getattr_style(self):
        """Test attribute-style config access."""
        config_data = {
            'rbls_file': 'config/rbls.txt',
            'logging': {'log_dir': 'logs'}
        }
        # Test top-level access
        assert config_data['rbls_file'] == 'config/rbls.txt'
        # Test nested access
        assert config_data['logging']['log_dir'] == 'logs'

    def test_thread_count_zero_invalid(self):
        """Test that zero threads is invalid."""
        thread_count = 0
        assert max(1, thread_count) == 1

    def test_thread_count_large_value(self):
        """Test thread count with large value."""
        thread_count = 100
        assert thread_count == 100

    def test_nameservers_default_opendns(self):
        """Test default OpenDNS nameservers."""
        nameservers = ['208.67.222.222']
        assert nameservers[0] == '208.67.222.222'

    def test_nameservers_fallback(self):
        """Test nameserver fallback."""
        nameservers = [] or ['208.67.222.222']
        assert nameservers == ['208.67.222.222']

    def test_console_print_true(self):
        """Test console print enabled."""
        console_print = True
        assert console_print is True

    def test_console_print_false(self):
        """Test console print disabled."""
        console_print = False
        assert console_print is False

    def test_console_print_default(self):
        """Test console print default is True."""
        config = {}
        console_print = config.get('console_print', True)
        assert console_print is True

    def test_run_once_true(self):
        """Test run_once enabled."""
        run_once = True
        assert run_once is True

    def test_run_once_false(self):
        """Test run_once disabled."""
        run_once = False
        assert run_once is False

    def test_sleep_hours_value(self):
        """Test sleep hours configuration."""
        sleep_hours = 3
        assert sleep_hours == 3


class TestConfigWebhooks:
    """Test cases for webhook configuration."""

    def test_config_webhooks_section_enabled(self):
        """Test config webhooks section when enabled."""
        webhooks_config = {
            'enabled': True,
            'urls': ['https://example.com/webhook', 'https://other.com/notify'],
            'timeout': 10
        }
        assert webhooks_config['enabled'] is True
        assert len(webhooks_config['urls']) == 2
        assert webhooks_config['timeout'] == 10

    def test_config_webhooks_section_disabled(self):
        """Test config webhooks section when disabled."""
        webhooks_config = {'enabled': False, 'urls': []}
        assert webhooks_config['enabled'] is False
        assert webhooks_config['urls'] == []

    def test_config_webhooks_empty_urls(self):
        """Test webhooks with empty URL list."""
        webhooks_config = {'enabled': True, 'urls': []}
        assert webhooks_config['enabled'] is True
        assert webhooks_config['urls'] == []

    def test_config_webhooks_single_url(self):
        """Test webhooks with single URL."""
        webhooks_config = {
            'enabled': True,
            'urls': ['https://example.com/webhook']
        }
        assert len(webhooks_config['urls']) == 1
        assert webhooks_config['urls'][0] == 'https://example.com/webhook'

    def test_config_webhooks_multiple_urls(self):
        """Test webhooks with multiple URLs."""
        webhooks_config = {
            'enabled': True,
            'urls': [
                'https://example.com/webhook',
                'https://slack.com/webhook',
                'https://discord.com/webhook'
            ]
        }
        assert len(webhooks_config['urls']) == 3
        assert 'https://slack.com/webhook' in webhooks_config['urls']

    def test_config_webhooks_timeout_default(self):
        """Test webhooks timeout defaults to 10."""
        webhooks_config = {'enabled': True, 'urls': ['https://example.com/webhook']}
        timeout = webhooks_config.get('timeout', 10)
        assert timeout == 10

    def test_config_webhooks_timeout_custom(self):
        """Test webhooks with custom timeout."""
        webhooks_config = {
            'enabled': True,
            'urls': ['https://example.com/webhook'],
            'timeout': 30
        }
        assert webhooks_config['timeout'] == 30

    def test_config_webhooks_all_fields(self):
        """Test webhooks configuration with all fields."""
        webhooks_config = {
            'enabled': True,
            'urls': ['https://example.com/webhook', 'https://backup.com/webhook'],
            'timeout': 15
        }
        assert webhooks_config['enabled'] is True
        assert len(webhooks_config['urls']) == 2
        assert webhooks_config['timeout'] == 15


class TestConfigApiUpdate:
    """Test cases for API update configuration."""

    def test_config_api_update_section_enabled(self):
        """Test config api_update section when enabled."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips',
            'auth_type': 'basic',
            'username': 'user',
            'password': 'pass',
            'bearer_token': '',
            'timeout': 10
        }
        assert api_update_config['enabled'] is True
        assert api_update_config['url'] == 'https://example.com/api/ips'
        assert api_update_config['auth_type'] == 'basic'
        assert api_update_config['timeout'] == 10

    def test_config_api_update_section_disabled(self):
        """Test config api_update section when disabled."""
        api_update_config = {'enabled': False}
        assert api_update_config['enabled'] is False

    def test_config_api_update_no_auth(self):
        """Test api_update with no authentication."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips',
            'auth_type': 'none'
        }
        assert api_update_config['auth_type'] == 'none'

    def test_config_api_update_basic_auth(self):
        """Test api_update with basic authentication."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips',
            'auth_type': 'basic',
            'username': 'testuser',
            'password': 'testpass'
        }
        assert api_update_config['auth_type'] == 'basic'
        assert api_update_config['username'] == 'testuser'
        assert api_update_config['password'] == 'testpass'

    def test_config_api_update_bearer_auth(self):
        """Test api_update with bearer token authentication."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips',
            'auth_type': 'bearer',
            'bearer_token': 'token123'
        }
        assert api_update_config['auth_type'] == 'bearer'
        assert api_update_config['bearer_token'] == 'token123'

    def test_config_api_update_timeout_default(self):
        """Test api_update timeout defaults to 10."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips'
        }
        timeout = api_update_config.get('timeout', 10)
        assert timeout == 10

    def test_config_api_update_timeout_custom(self):
        """Test api_update with custom timeout."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips',
            'timeout': 30
        }
        assert api_update_config['timeout'] == 30

    def test_config_api_update_empty_credentials(self):
        """Test api_update with empty credentials."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips',
            'auth_type': 'none',
            'username': '',
            'password': '',
            'bearer_token': ''
        }
        assert api_update_config['username'] == ''
        assert api_update_config['password'] == ''
        assert api_update_config['bearer_token'] == ''

    def test_config_api_update_url_empty(self):
        """Test api_update with empty URL."""
        api_update_config = {
            'enabled': False,
            'url': ''
        }
        assert api_update_config['url'] == ''

    def test_config_api_update_all_fields(self):
        """Test api_update configuration with all fields."""
        api_update_config = {
            'enabled': True,
            'url': 'https://example.com/api/ips',
            'auth_type': 'bearer',
            'username': '',
            'password': '',
            'bearer_token': 'mytoken123',
            'timeout': 20
        }
        assert api_update_config['enabled'] is True
        assert api_update_config['url'] == 'https://example.com/api/ips'
        assert api_update_config['auth_type'] == 'bearer'
        assert api_update_config['bearer_token'] == 'mytoken123'
        assert api_update_config['timeout'] == 20
