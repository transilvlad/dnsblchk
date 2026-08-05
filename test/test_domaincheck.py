from unittest.mock import MagicMock, patch

import dns.resolver

from domaincheck import DomainResolver


class TestDomainResolver:
    """Test cases for DomainResolver."""

    def test_domain_resolver_initialization_defaults(self):
        resolver = DomainResolver()
        assert resolver.nameservers == ['208.67.222.222', '208.67.220.220']

    def test_get_registrable_apex_simple_domain(self):
        resolver = DomainResolver()
        assert resolver.get_registrable_apex('mail.example.com') == 'example.com'

    def test_get_registrable_apex_known_multi_label_suffix(self):
        resolver = DomainResolver()
        assert resolver.get_registrable_apex('mx.example.co.uk') == 'example.co.uk'

    def test_get_registrable_apex_normalizes_domain(self):
        resolver = DomainResolver()
        assert resolver.get_registrable_apex('Mail.Example.COM.') == 'example.com'

    @patch('domaincheck.dns.resolver.Resolver')
    def test_resolve_ptr_returns_normalized_hostname(self, mock_resolver_class):
        resolver = DomainResolver(nameservers=['1.1.1.1'])
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver

        mock_rdata = MagicMock()
        mock_rdata.target = 'Mail.Example.COM.'
        mock_resolver.resolve.return_value = [mock_rdata]

        assert resolver.resolve_ptr('192.0.2.10') == 'mail.example.com'
        assert mock_resolver.nameservers == ['1.1.1.1']

    @patch('domaincheck.dns.resolver.Resolver')
    def test_resolve_ptr_missing_returns_none(self, mock_resolver_class):
        resolver = DomainResolver()
        mock_resolver = MagicMock()
        mock_resolver_class.return_value = mock_resolver
        mock_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()

        assert resolver.resolve_ptr('192.0.2.10') is None

    def test_derive_check_targets_returns_ptr_and_apex(self):
        resolver = DomainResolver()
        resolver.resolve_ptr = MagicMock(return_value='mail.example.com')

        assert resolver.derive_check_targets('192.0.2.10') == {
            ('mail.example.com', 'ptr'),
            ('example.com', 'apex'),
        }

    def test_derive_check_targets_without_ptr_returns_empty_set(self):
        resolver = DomainResolver()
        resolver.resolve_ptr = MagicMock(return_value=None)

        assert resolver.derive_check_targets('192.0.2.10') == set()
