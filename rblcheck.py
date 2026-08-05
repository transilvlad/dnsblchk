from typing import Union, List

import dns.resolver
import dns.reversename


class RBLCheck:
    """Checks if IP addresses or domains are listed on DNS block list servers."""

    def __init__(self, nameservers: list = None):
        """
        Initialize the DNS block list checker.

        Args:
            nameservers: List of DNS nameservers to use for queries.
                        Defaults to OpenDNS servers if not provided.
                        Example: ['208.67.222.222', '208.67.220.220']
        """
        # List of DNS nameservers to query for block list checks.
        # Uses OpenDNS servers by default for redundancy.
        if nameservers is None:
            nameservers = ['208.67.222.222', '208.67.220.220']
        self.nameservers = nameservers

    def _resolver(self) -> dns.resolver.Resolver:
        """Create and configure a resolver instance."""
        resolver = dns.resolver.Resolver()
        resolver.nameservers = self.nameservers
        return resolver

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
            # Reverse the IP address for the DNS query format.
            if '.' in ip:  # IPv4 address format.
                # Handle IPv4-mapped IPv6 addresses by stripping prefix.
                ip = ip.replace('::ffff:', '')
                # Reverse octets for DNS reverse lookup.
                rev_ip = '.'.join(reversed(ip.split('.')))
            else:  # IPv6 address format.
                # Convert IPv6 address to reverse DNS notation.
                rev_ip = dns.reversename.from_address(ip).to_text(omit_final_dot=True)

            # Construct the query name for the DNS RBL server.
            query_name = f"{rev_ip}.{server}"

            # Create resolver instance for DNS queries.
            resolver = self._resolver()

            # Query the DNS RBL server for an A record (contains return code).
            answers = resolver.resolve(query_name, 'A')

            # IP is listed, prepare the result list.
            result = [server]
            # Extract response address from DNS RBL return value.
            for rdata in answers:
                result.append(rdata.address)
            # Append 'R' to indicate result (listing flag).
            result.append('R')

            return result

        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
            # Not listed or other DNS resolution error; NXDOMAIN means IP is not on list.
            return False
        except Exception:
            # Any other exception means we can't be sure, so assume not listed.
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
            resolver = self._resolver()
            answers = resolver.resolve(query_name, 'A')

            result = [server]
            for rdata in answers:
                result.append(rdata.address)

            if include_txt_context:
                try:
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

        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
            return False
        except Exception:
            return False
