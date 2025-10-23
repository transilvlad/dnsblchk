from typing import Union, List

import dns.resolver
import dns.reversename


class DNSRBLChecker:
    """Checks if IP addresses are blacklisted on DNSBL servers."""

    def __init__(self, nameserver: str = '208.67.222.222'):
        """
        Initialize the DNSRBL checker.

        :param nameserver: The DNS nameserver to use for queries (default: OpenDNS)
        """
        self.nameserver = nameserver

    def check(self, ip: str, server: str) -> Union[bool, List[str]]:
        """
        Checks if an IP address is blacklisted on a DNSBL server.

        :param ip: The IP address to check.
        :param server: The DNSBL server to query.
        :return: A list with server, response address and 'R' if listed, otherwise False.
        """
        try:
            # Reverse the IP address for the DNS query
            if '.' in ip:  # IPv4
                # Handle IPv4-mapped IPv6 addresses
                ip = ip.replace('::ffff:', '')
                rev_ip = '.'.join(reversed(ip.split('.')))
            else:  # IPv6
                rev_ip = dns.reversename.from_address(ip).to_text(omit_final_dot=True)

            query_name = f"{rev_ip}.{server}"

            resolver = dns.resolver.Resolver()
            resolver.nameservers = [self.nameserver]

            # The A record contains the return code for blacklists
            answers = resolver.resolve(query_name, 'A')

            # The IP is listed, prepare the result list
            result = [server]
            for rdata in answers:
                result.append(rdata.address)
            result.append('R')  # As per some conventions

            return result

        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
            # Not listed or other DNS resolution error
            return False
        except Exception:
            # Any other exception means we can't be sure, so assume not listed
            return False
