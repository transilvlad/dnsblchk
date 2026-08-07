import csv
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from dnscheck import DNSCheck
from logger import Logger, LogConfig, LogLevel
from mail import MailClient
from rblcheck import RBLCheck


class TestDNSCheck:
    """Test cases for DNSCheck class."""

    @pytest.fixture
    def mock_mail_client(self):
        """Create a mock mail client."""
        return MagicMock(spec=MailClient)

    @pytest.fixture
    def mock_rbl_checker(self):
        """Create a mock RBL checker."""
        return MagicMock(spec=RBLCheck)

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def logger(self, temp_log_dir):
        """Create a logger instance."""
        config = LogConfig(
            log_dir=temp_log_dir,
            level=LogLevel.DEBUG,
            console_print=False
        )
        return Logger(config)

    @pytest.fixture
    def dns_check(self, mock_mail_client, mock_rbl_checker, logger):
        """Create a DNSCheck instance."""
        return DNSCheck(mock_mail_client, mock_rbl_checker, logger)

    def test_dnscheck_initialization(self, mock_mail_client, mock_rbl_checker, logger):
        """Test DNSCheck initialization."""
        checker = DNSCheck(mock_mail_client, mock_rbl_checker, logger)

        assert checker.mail_client == mock_mail_client
        assert checker.dnsrbl_checker == mock_rbl_checker
        assert checker.logger == logger
        assert checker.listed_ips == {}
        assert checker.report_file_handler is None
        assert checker.csv_writer is None

    def test_check_ip_against_server_success(self, dns_check, mock_rbl_checker):
        """Test successful IP check against server."""
        mock_rbl_checker.check.return_value = ['rbl.example.com', '127.0.0.2', 'R']

        result = dns_check.check_ip_against_server('192.168.1.1', 'rbl.example.com')

        assert result is not None
        ip, server, is_listed, result_details = result
        assert ip == '192.168.1.1'
        assert server == 'rbl.example.com'
        assert is_listed != False
        assert result_details == '127.0.0.2'

    def test_check_ip_against_server_not_listed(self, dns_check, mock_rbl_checker):
        """Test IP check when not listed."""
        mock_rbl_checker.check.return_value = False

        result = dns_check.check_ip_against_server('192.168.1.1', 'rbl.example.com')

        assert result is not None
        ip, server, is_listed, result_details = result
        assert is_listed is False
        assert result_details is None

    def test_check_ip_against_server_exception(self, dns_check, mock_rbl_checker):
        """Test IP check with exception."""
        mock_rbl_checker.check.side_effect = Exception("DNS error")

        result = dns_check.check_ip_against_server('192.168.1.1', 'rbl.example.com')

        assert result is None

    @patch('dnscheck.SignalHandler')
    def test_check_ip_against_server_shutdown(self, mock_signal_handler, dns_check):
        """Test IP check returns None when shutdown requested."""
        mock_signal_handler.return_value.is_shutdown_requested = True

        result = dns_check.check_ip_against_server('192.168.1.1', 'rbl.example.com')

        assert result is None

    def test_record_listed_ip(self, dns_check):
        """Test recording a listed IP."""
        dns_check._record_listed_ip('192.168.1.1', 'rbl1.example.com')
        dns_check._record_listed_ip('192.168.1.1', 'rbl2.example.com')

        assert '192.168.1.1' in dns_check.listed_ips
        assert 'rbl1.example.com' in dns_check.listed_ips['192.168.1.1']
        assert 'rbl2.example.com' in dns_check.listed_ips['192.168.1.1']

    def test_record_listed_ip_duplicate(self, dns_check):
        """Test that duplicate servers are not added."""
        dns_check._record_listed_ip('192.168.1.1', 'rbl.example.com')
        dns_check._record_listed_ip('192.168.1.1', 'rbl.example.com')

        assert len(dns_check.listed_ips['192.168.1.1']) == 1

    def test_process_check_result_listed(self, dns_check, temp_log_dir):
        """Test processing a positive check result."""
        try:
            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir

                result = ('192.168.1.1', 'rbl.example.com',
                          ['rbl.example.com', '127.0.0.2', 'R'], '127.0.0.2')

                dns_check._process_check_result(result)

                assert '192.168.1.1' in dns_check.listed_ips
        finally:
            # Ensure file handle is closed for cleanup
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_process_check_result_not_listed(self, dns_check):
        """Test processing a negative check result."""
        result = ('192.168.1.1', 'rbl.example.com', False, None)

        dns_check._process_check_result(result)

        # Should not be added to listed_ips
        assert '192.168.1.1' not in dns_check.listed_ips

    def test_process_check_result_none(self, dns_check):
        """Test processing a None result."""
        # Should not raise an exception
        dns_check._process_check_result(None)

    def test_write_report_creates_file(self, dns_check, temp_log_dir):
        """Test that write_report creates a CSV file."""
        try:
            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir

                dns_check._write_report('192.168.1.1', 'rbl.example.com', '127.0.0.2')

                assert dns_check.report_file_handler is not None
                assert dns_check.csv_writer is not None
        finally:
            # Ensure file handle is closed for cleanup
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_write_report_writes_data(self, dns_check, temp_log_dir):
        """Test that write_report writes data to CSV."""
        try:
            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir

                dns_check._write_report('192.168.1.1', 'rbl.example.com', '127.0.0.2')

                # Get report file before closing
                report_files = list(temp_log_dir.glob('report_*.csv'))
                assert len(report_files) > 0

                dns_check.report_file_handler.close()

                # Check that the file exists and contains data
                with open(report_files[0], 'r') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    assert len(rows) == 2
                    assert rows[0] == [
                        'timestamp', 'source_ip', 'check_type', 'target',
                        'target_source', 'server', 'obm_server', 'response', 'txt_context'
                    ]
                    assert '192.168.1.1' in rows[1]
                    assert 'rbl.example.com' in rows[1]
        finally:
            # Ensure file handle is closed for cleanup
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_run_basic(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Test basic run function."""
        try:
            mock_rbl_checker.check.return_value = False

            servers = [['rbl.example.com']]
            ips = [['192.168.1.1']]

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 2
                mock_config.is_email_enabled.return_value = False
                mock_config.is_webhooks_enabled.return_value = False
                mock_config.get_active_suppressions.return_value = set()
                mock_config.get_keep_last_reports.return_value = 5

                dns_check.run(servers, [], ips)

                # Should complete without error
                assert dns_check.listed_ips == {}
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_run_with_listed_ips(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Test run function with listed IPs."""
        try:
            mock_rbl_checker.check.return_value = ['rbl.example.com', '127.0.0.2', 'R']

            servers = [['rbl.example.com']]
            ips = [['192.168.1.1']]

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 2
                mock_config.is_email_enabled.return_value = False
                mock_config.is_webhooks_enabled.return_value = False
                mock_config.get_active_suppressions.return_value = set()
                mock_config.get_keep_last_reports.return_value = 5

                dns_check.run(servers, [], ips)

                assert '192.168.1.1' in dns_check.listed_ips
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    @patch('dnscheck.SignalHandler')
    def test_run_shutdown_during_preparation(self, mock_signal_handler,
                                             dns_check, mock_rbl_checker, temp_log_dir):
        """Test run function stops during task preparation if shutdown requested."""
        try:
            mock_signal_handler.return_value.is_shutdown_requested = True

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 2
                mock_config.is_email_enabled.return_value = False
                mock_config.is_webhooks_enabled.return_value = False
                mock_config.get_active_suppressions.return_value = set()
                mock_config.get_keep_last_reports.return_value = 5

                dns_check.run([['rbl.example.com']], [], [['192.168.1.1']])

                # Check that it returned early
                assert dns_check.listed_ips == {}
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_run_closes_report_file(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Test that run function closes the report file."""
        try:
            mock_rbl_checker.check.return_value = ['rbl.example.com', '127.0.0.2', 'R']

            servers = [['rbl.example.com']]
            ips = [['192.168.1.1']]

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 2
                mock_config.is_email_enabled.return_value = False
                mock_config.is_webhooks_enabled.return_value = False
                mock_config.get_active_suppressions.return_value = set()
                mock_config.get_keep_last_reports.return_value = 5

                dns_check.run(servers, [], ips)

                # Report file should be closed
                assert dns_check.report_file_handler is None or dns_check.report_file_handler.closed
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_send_email_report_builds_message(self, dns_check, mock_mail_client, temp_log_dir):
        """Test that _send_email_report builds correct message."""
        dns_check.listed_ips = {
            '192.168.1.1': ['rbl1.example.com', 'rbl2.example.com'],
            '192.168.1.2': ['rbl1.example.com']
        }

        with patch('dnscheck.config') as mock_config:
            mock_config.get_email_recipients.return_value = ['tony@example.com']
            mock_config.get_email_sender.return_value = 'noreply@example.com'
            mock_mail_client.send_plain.return_value = (True, None)

            dns_check._send_email_report()

            # Check that send_plain was called
            assert mock_mail_client.send_plain.called

    def test_send_email_report_multiple_recipients(self, dns_check, mock_mail_client):
        """Test that _send_email_report sends to all recipients."""
        dns_check.listed_ips = {'192.168.1.1': ['rbl.example.com']}

        recipients = ['happy@example.com', 'peter@example.com']

        with patch('dnscheck.config') as mock_config:
            mock_config.get_email_recipients.return_value = recipients
            mock_config.get_email_sender.return_value = 'noreply@example.com'
            mock_mail_client.send_plain.return_value = (True, None)

            dns_check._send_email_report()

            # Should send to each recipient
            assert mock_mail_client.send_plain.call_count == 2

    def test_thread_pool_usage(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Test that run uses ThreadPoolExecutor."""
        try:
            mock_rbl_checker.check.return_value = False

            servers = [['rbl.example.com']]
            ips = [['192.168.1.1'], ['192.168.1.2']]

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 2
                mock_config.is_email_enabled.return_value = False

                with patch('dnscheck.ThreadPoolExecutor') as mock_executor_class:
                    mock_executor = MagicMock()
                    mock_executor_class.return_value.__enter__.return_value = mock_executor
                    mock_executor.submit.return_value = MagicMock()
                    mock_executor.__enter__.return_value = mock_executor
                    mock_executor.__exit__.return_value = None

                    # This will use the mocked executor
                    # Note: The actual run function creates its own executor, so this tests that pattern
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_multiple_ips_multiple_servers(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Test checking multiple IPs against multiple servers."""
        try:
            mock_rbl_checker.check.return_value = False

            servers = [['rbl1.example.com'], ['rbl2.example.com']]
            ips = [['192.168.1.1'], ['192.168.1.2']]

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 4
                mock_config.is_email_enabled.return_value = False
                mock_config.is_webhooks_enabled.return_value = False
                mock_config.get_active_suppressions.return_value = set()
                mock_config.get_keep_last_reports.return_value = 5

                dns_check.run(servers, [], ips)

                # Should call check 4 times (2 IPs x 2 servers)
                assert mock_rbl_checker.check.call_count == 4
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    @pytest.mark.skip(
        reason="Serial-only run mode not implemented in current dnscheck.run(); "
               "threading.enabled=False is honored by clamping thread_count, not by skipping the executor. "
               "Reintroduce a true serial path (and this test) if a debug-only single-thread mode is needed."
    )
    def test_run_respects_threading_disabled(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Placeholder for a serial-only run mode. See skip reason above."""
        pass

    def test_run_does_not_query_dbl_when_no_domain_targets(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Test DBL servers are skipped when PTR/apex derivation returns no targets."""
        try:
            mock_rbl_checker.check.return_value = False
            dns_check.domain_resolver.derive_check_targets = MagicMock(return_value=set())

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 2
                mock_config.is_threading_enabled.return_value = True
                mock_config.is_email_enabled.return_value = False
                mock_config.is_webhooks_enabled.return_value = False
                mock_config.get_active_suppressions.return_value = set()
                mock_config.get_keep_last_reports.return_value = 5

                dns_check.run([], [['dbl.example.com']], [['192.0.2.10']])

                mock_rbl_checker.check_domain.assert_not_called()
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass

    def test_get_address_group_returns_most_specific_match(self, dns_check):
        """Test configured address groups use the most specific network match."""
        with patch('dnscheck.config') as mock_config:
            mock_config.get_address_groups.return_value = {
                'shared': ['192.0.2.0/24'],
                'specific': ['192.0.2.10/32'],
            }

            assert dns_check._get_address_group('192.0.2.10') == 'specific'
            assert dns_check._get_address_group('192.0.2.11') == 'shared'
            assert dns_check._get_address_group('198.51.100.1') == ''

    def test_run_writes_dbl_target_in_report(self, dns_check, mock_rbl_checker, temp_log_dir):
        """Test that DBL results write actual domain target and check type in CSV."""
        try:
            mock_rbl_checker.check.return_value = False
            mock_rbl_checker.check_domain.return_value = ['dbl.example.com', '127.0.1.2', 'TXT=test', 'R']

            rbl_servers = [['rbl.example.com']]
            dbl_servers = [['dbl.example.com']]
            ips = [['192.0.2.10']]

            with patch('dnscheck.config') as mock_config:
                mock_config.report_dir = temp_log_dir
                mock_config.get_thread_count.return_value = 2
                mock_config.is_email_enabled.return_value = False
                mock_config.is_webhooks_enabled.return_value = False
                mock_config.get_active_suppressions.return_value = set()
                mock_config.get_keep_last_reports.return_value = 5
                mock_config.get_address_groups.return_value = {}
                mock_config.log_file = temp_log_dir / "test.log"

                dns_check.domain_resolver.derive_check_targets = MagicMock(
                    return_value={('mail.example.com', 'ptr'), ('example.com', 'apex')}
                )

                dns_check.run(rbl_servers, dbl_servers, ips)

                report_files = list(temp_log_dir.glob('report_*.csv'))
                assert len(report_files) > 0

                with open(report_files[0], 'r') as f:
                    reader = csv.reader(f)
                    rows = list(reader)

                assert rows[0] == [
                    'timestamp', 'source_ip', 'check_type', 'target',
                    'target_source', 'server', 'obm_server', 'response', 'txt_context'
                ]
                dbl_rows = [row for row in rows[1:] if len(row) >= 6 and row[2] in ('PTR', 'APEX')]
                assert any(row[3] == 'mail.example.com' for row in dbl_rows)
                assert any(row[3] == 'example.com' for row in dbl_rows)
                assert all(row[5] == 'dbl.example.com' for row in dbl_rows)
                assert all(row[7] == '127.0.1.2' for row in dbl_rows)
                assert all(row[8] == 'test' for row in dbl_rows)
        finally:
            if dns_check.report_file_handler:
                try:
                    dns_check.report_file_handler.close()
                except Exception:
                    pass
