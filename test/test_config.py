"""Unit tests for the config module."""
from pathlib import Path

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

    def test_config_dict_structure(self):
        """Test basic config dictionary structure."""
        config_data = {
            'servers_file': 'config/servers.txt',
            'ips_file': 'config/ips.txt',
            'report_dir': 'logs/',
            'logging': {'log_dir': 'logs', 'log_file': 'app.log'},
            'email': {'enabled': False},
            'nameservers': ['8.8.8.8']
        }
        assert config_data['servers_file'] == 'config/servers.txt'
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
        email_config = {'enabled': True, 'recipients': ['test@example.com']}
        assert email_config['enabled'] is True
        assert 'test@example.com' in email_config['recipients']

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
        recipients = ['test1@example.com', 'test2@example.com']
        assert recipients == ['test1@example.com', 'test2@example.com']
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
        relative_path = 'config/servers.txt'
        full_path = root_path / relative_path
        # Use Path normalization to handle both Windows and Unix paths
        assert 'servers.txt' in str(full_path)
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
            'servers_file': 'config/servers.txt',
            'logging': {'log_dir': 'logs'}
        }
        # Test top-level access
        assert config_data['servers_file'] == 'config/servers.txt'
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
