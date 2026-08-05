"""Utilities for domain resolution, normalization, and apex extraction."""

from typing import Optional, Set, Tuple

import dns.rdatatype
import dns.resolver
import dns.reversename


class DomainResolver:
    """Resolves and normalizes domain names for DBL checking."""

    def __init__(self, nameservers: list = None):
        """
        Initialize the domain resolver.

        Args:
            nameservers: List of DNS nameservers to use.
        """
        if nameservers is None:
            nameservers = ['208.67.222.222', '208.67.220.220']
        self.nameservers = nameservers

    def _resolver(self) -> dns.resolver.Resolver:
        """Create and configure a resolver instance."""
        resolver = dns.resolver.Resolver()
        resolver.nameservers = self.nameservers
        return resolver

    def resolve_ptr(self, ip: str) -> Optional[str]:
        """
        Resolve reverse DNS (PTR) for an IP address.

        Args:
            ip: IP address (IPv4 or IPv6).

        Returns:
            PTR hostname (normalized/lowercased) or None if not found.
        """
        try:
            resolver = self._resolver()
            ptr_name = dns.reversename.from_address(ip)
            answers = resolver.resolve(ptr_name, dns.rdatatype.PTR)
            for rdata in answers:
                hostname = str(rdata.target).rstrip('.')
                return hostname.lower()
            return None
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
            return None
        except Exception:
            return None

    def get_registrable_apex(self, domain: str) -> str:
        """
        Extract the registrable apex (base domain) from a hostname.

        For simple cases, this returns the last two labels (example.com).
        For known multi-label public suffixes, this returns the last three labels.
        """
        domain = domain.strip().lower().rstrip('.')
        if not domain:
            return domain

        labels = domain.split('.')
        known_suffixes = {'co.uk', 'co.jp', 'com.au', 'com.br', 'co.nz', 'ac.uk', 'gov.uk'}

        if len(labels) >= 3:
            two_label_suffix = '.'.join(labels[-2:])
            if two_label_suffix in known_suffixes:
                return '.'.join(labels[-3:])

        if len(labels) >= 2:
            return '.'.join(labels[-2:])

        return domain

    def derive_check_targets(self, ip: str) -> Set[Tuple[str, str]]:
        """
        Derive DBL check targets (PTR hostname and apex) for an IP.

        Args:
            ip: IP address to check.

        Returns:
            Set of (domain, 'ptr' | 'apex') tuples. Empty set if PTR is unavailable.
        """
        targets = set()
        ptr = self.resolve_ptr(ip)
        if not ptr:
            return targets

        targets.add((ptr, 'ptr'))
        apex = self.get_registrable_apex(ptr)
        if apex != ptr:
            targets.add((apex, 'apex'))

        return targets
