from unittest.mock import patch, MagicMock

import dns.resolver
import dns.reversename

from rblcheck import RBLCheck


class TestRBLCheck:
    """Test cases for RBLCheck class."""

    def test_rbl_check_initialization_defaults(self):
        """Test RBLCheck initialization with default nameservers."""
        checker = RBLCheck()
        assert checker.nameservers == ['208.67.222.222', '208.67.220.220']

    def test_rbl_check_initialization_custom_nameservers(self):
        """Test RBLCheck initialization with custom nameservers."""
        custom_ns = ['8.8.8.8', '8.8.4.4']
        checker = RBLCheck(nameservers=custom_ns)
        assert checker.nameservers == custom_ns

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv4_listed(self, mock_resolver_class):
        """Test checking IPv4 address that is listed."""
        checker = RBLCheck()

        # Mock the resolver
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        # Mock the response
        mock_rdata = MagicMock()
        mock_rdata.address = '127.0.0.2'
        mock_resolver.resolve.return_value = [mock_rdata]

        result = checker.check('192.168.1.1', 'rbl.example.com')

        assert result != False
        assert 'rbl.example.com' in result
        assert '127.0.0.2' in result
        assert 'R' in result

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv4_not_listed(self, mock_resolver_class):
        """Test checking IPv4 address that is not listed."""
        checker = RBLCheck()

        # Mock the resolver to raise NXDOMAIN
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        result = checker.check('192.168.1.1', 'rbl.example.com')

        assert result is False

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv4_no_answer(self, mock_resolver_class):
        """Test checking IPv4 with NoAnswer response."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NoAnswer()

        result = checker.check('192.168.1.1', 'rbl.example.com')

        assert result is False

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv4_timeout(self, mock_resolver_class):
        """Test checking IPv4 with timeout."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.exception.Timeout()

        result = checker.check('192.168.1.1', 'rbl.example.com')

        assert result is False

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv4_generic_exception(self, mock_resolver_class):
        """Test checking IPv4 with generic exception."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = Exception("Unknown error")

        result = checker.check('192.168.1.1', 'rbl.example.com')

        assert result is False

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv6_listed(self, mock_resolver_class):
        """Test checking IPv6 address that is listed."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        mock_rdata = MagicMock()
        mock_rdata.address = '127.0.0.2'
        mock_resolver.resolve.return_value = [mock_rdata]

        result = checker.check('2001:4860:4860::8888', 'rbl.example.com')

        assert result != False
        assert 'rbl.example.com' in result
        assert 'R' in result

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv6_not_listed(self, mock_resolver_class):
        """Test checking IPv6 address that is not listed."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        result = checker.check('2001:4860:4860::8888', 'rbl.example.com')

        assert result is False

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_ipv4_mapped_ipv6(self, mock_resolver_class):
        """Test checking IPv4-mapped IPv6 address."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        mock_rdata = MagicMock()
        mock_rdata.address = '127.0.0.2'
        mock_resolver.resolve.return_value = [mock_rdata]

        result = checker.check('::ffff:192.168.1.1', 'rbl.example.com')

        assert result != False

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_uses_custom_nameservers(self, mock_resolver_class):
        """Test that check uses the configured nameservers."""
        custom_ns = ['1.1.1.1', '1.0.0.1']
        checker = RBLCheck(nameservers=custom_ns)

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        checker.check('192.168.1.1', 'rbl.example.com')

        # Check that nameservers were set
        assert mock_resolver.nameservers == custom_ns

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_multiple_return_addresses(self, mock_resolver_class):
        """Test checking IP with multiple return addresses."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        # Mock multiple return addresses
        mock_rdata1 = MagicMock()
        mock_rdata1.address = '127.0.0.2'
        mock_rdata2 = MagicMock()
        mock_rdata2.address = '127.0.0.3'
        mock_resolver.resolve.return_value = [mock_rdata1, mock_rdata2]

        result = checker.check('192.168.1.1', 'rbl.example.com')

        assert len(result) >= 3
        assert '127.0.0.2' in result
        assert '127.0.0.3' in result
        assert 'R' in result

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_query_name_format_ipv4(self, mock_resolver_class):
        """Test that query name is formatted correctly for IPv4."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        checker.check('192.168.1.1', 'rbl.example.com')

        # Check the query name format
        call_args = mock_resolver.resolve.call_args
        query_name = call_args[0][0]

        # Should be in format: 1.1.168.192.rbl.example.com
        assert query_name.endswith('rbl.example.com')
        assert query_name.startswith('1.1.168.192')

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_a_record_query(self, mock_resolver_class):
        """Test that check queries for A record."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        checker.check('192.168.1.1', 'rbl.example.com')

        # Check that A record was requested
        call_args = mock_resolver.resolve.call_args
        assert call_args[0][1] == 'A'

    def test_check_empty_nameservers(self):
        """Test that empty nameservers list defaults properly."""
        checker = RBLCheck(nameservers=[])
        # Empty list should still be set
        assert checker.nameservers == []

    @patch('rblcheck.dns.resolver.Resolver')
    def test_check_result_structure(self, mock_resolver_class):
        """Test the structure of the return value."""
        checker = RBLCheck()

        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        mock_rdata = MagicMock()
        mock_rdata.address = '127.0.0.2'
        mock_resolver.resolve.return_value = [mock_rdata]

        result = checker.check('192.168.1.1', 'rbl.example.com')

        assert isinstance(result, list)
        assert result[0] == 'rbl.example.com'
        assert result[-1] == 'R'
