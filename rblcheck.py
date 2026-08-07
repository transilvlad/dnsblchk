from typing import List, Optional, Union

import dns.resolver
import dns.reversename


# RFC 5782 §5: DNSxL responses in 127.255.255.0/24 signal errors, not listings.
# Spamhaus specifically uses:
#   127.255.255.252  typing error / test address
#   127.255.255.253  open-resolver test (query originated from an open resolver)
#   127.255.255.254  anonymous query blocked (public/large DNS resolver)
#   127.255.255.255  excessive queries — client is rate-limited
def _is_error_response(address: str) -> bool:
    return isinstance(address, str) and address.startswith('127.255.255.')


class RBLCheck:
    """Checks if IP addresses are listed on DNS RBL/DBL servers."""

    def __init__(
        self,
        nameservers: list = None,
        nameservers_confirm: list = None,
        logger=None,
    ):
        """
        Initialize the DNS RBL/DBL Checker.

        Args:
            nameservers: Primary DNS resolvers used for every query.
            nameservers_confirm: Optional confirmation resolvers. If non-empty,
                a positive result from the primary is re-queried via these
                resolvers. The listing is only reported when the confirm
                resolvers agree; otherwise it is dropped and a warning is
                logged.
            logger: Optional Logger instance used for DISPUTED / RBL-error
                warnings. Silent if not provided.
        """
        if nameservers is None:
            nameservers = ['208.67.222.222', '208.67.220.220']
        self.nameservers = nameservers
        self.nameservers_confirm = list(nameservers_confirm or [])
        self.logger = logger

    def _resolver(self, use_confirm: bool = False) -> dns.resolver.Resolver:
        """Create a resolver instance bound to primary or confirm nameservers."""
        resolver = dns.resolver.Resolver()
        resolver.nameservers = (
            self.nameservers_confirm if use_confirm else self.nameservers
        )
        return resolver

    def _log_warning(self, msg: str):
        if self.logger is not None:
            try:
                self.logger.log_warning(msg)
            except Exception:
                pass

    def _query_addresses(
        self,
        query_name: str,
        use_confirm: bool = False,
    ) -> Optional[List[str]]:
        """Return list of A-record addresses excluding RBL error codes.

        Returns None on NXDOMAIN / NoAnswer / Timeout / any DNS error.
        Returns [] if every answer was a 127.255.255.x error code.
        """
        try:
            resolver = self._resolver(use_confirm=use_confirm)
            answers = resolver.resolve(query_name, 'A')
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
            return None
        except Exception:
            return None

        raw = [rdata.address for rdata in answers]
        listed = [a for a in raw if not _is_error_response(a)]
        if raw and not listed:
            self._log_warning(
                f"RBL_ERROR_CODE: {query_name} returned only error responses "
                f"{raw} via {'confirm' if use_confirm else 'primary'} resolvers "
                f"{self.nameservers_confirm if use_confirm else self.nameservers} — treating as not listed"
            )
        return listed

    def _confirm_listing(self, query_name: str) -> bool:
        """Return True if confirm resolvers also see a valid listing.

        Only called after primary resolver saw a valid listing. If no confirm
        resolvers are configured, returns True (feature disabled).
        """
        if not self.nameservers_confirm:
            return True
        confirmed = self._query_addresses(query_name, use_confirm=True)
        if confirmed:
            return True
        self._log_warning(
            f"DISPUTED: {query_name} listed via primary {self.nameservers} "
            f"but not confirmed via {self.nameservers_confirm} — dropping"
        )
        return False

    def check(self, ip: str, server: str) -> Union[bool, List[str]]:
        """Backward-compatible alias for IP-based RBL checks."""
        return self.check_ip(ip, server)

    def check_ip(self, ip: str, server: str) -> Union[bool, List[str]]:
        """
        Checks if an IP address is listed on a DNS RBL server.
        Uses reverse DNS lookup to query the RBL server.

        Args:
            ip: The IP address to check.
            server: The DNS RBL server to query.

        Returns:
            A list with server, response address and 'R' if listed, otherwise False.
        """
        try:
            if '.' in ip:  # IPv4 address format.
                ip = ip.replace('::ffff:', '')
                rev_ip = '.'.join(reversed(ip.split('.')))
            else:  # IPv6 address format.
                rev_ip = dns.reversename.from_address(ip).to_text(omit_final_dot=True)

            query_name = f"{rev_ip}.{server}"

            listed = self._query_addresses(query_name)
            if not listed:
                return False

            if not self._confirm_listing(query_name):
                return False

            result = [server, *listed, 'R']
            return result

        except Exception:
            return False

    def check_domain(self, domain: str, server: str, include_txt_context: bool = True) -> Union[bool, List[str]]:
        """
        Checks if a domain is listed on a DNS DBL server.

        Args:
            domain: Domain name to check.
            server: DBL server zone to query.
            include_txt_context: If True, also attempts TXT lookup for context.

        Returns:
            A list with server, response details and 'R' if listed, otherwise False.
        """
        try:
            normalized_domain = domain.strip().lower().rstrip('.')
            if not normalized_domain:
                return False

            query_name = f"{normalized_domain}.{server}"

            listed = self._query_addresses(query_name)
            if not listed:
                return False

            if not self._confirm_listing(query_name):
                return False

            result = [server, *listed]

            if include_txt_context:
                try:
                    resolver = self._resolver()
                    txt_answers = resolver.resolve(query_name, 'TXT')
                    txt_values = []
                    for txt in txt_answers:
                        if hasattr(txt, "strings") and txt.strings:
                            txt_values.extend(
                                s.decode(errors='ignore')
                                for s in txt.strings
                                if isinstance(s, (bytes, bytearray))
                            )
                        else:
                            txt_values.append(txt.to_text().strip('"'))
                    if txt_values:
                        result.append(f"TXT={' | '.join(txt_values)}")
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
                    pass

            result.append('R')
            return result

        except Exception:
            return False
