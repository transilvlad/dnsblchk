from typing import Union, List

import dns.resolver
import dns.reversename


class RBLCheck:
    """Checks if IP addresses are blacklisted on DNSBL servers."""

    def __init__(self, nameserver: str = '208.67.222.222'):
        """
        Initialize the DNSRBL checker.

        Args:
            nameserver: The DNS nameserver to use for queries (default: OpenDNS).
        """
        # DNS nameserver to query for blacklist checks (OpenDNS by default).
        self.nameserver = nameserver

    def check(self, ip: str, server: str) -> Union[bool, List[str]]:
        """
        Checks if an IP address is blacklisted on a DNSBL server.
        Uses reverse DNS lookup to query the blacklist server.

        Args:
            ip: The IP address to check.
            server: The DNSBL server to query.

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

            # Construct the query name for the DNSBL server.
            query_name = f"{rev_ip}.{server}"

            # Create resolver instance for DNS queries.
            resolver = dns.resolver.Resolver()
            # Set the nameserver to use for this query.
            resolver.nameservers = [self.nameserver]

            # Query the DNSBL server for an A record (contains return code).
            answers = resolver.resolve(query_name, 'A')

            # IP is listed, prepare the result list.
            result = [server]
            # Extract response address from DNSBL return value.
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
