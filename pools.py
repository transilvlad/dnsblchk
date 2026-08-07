import ipaddress
import json
from pathlib import Path
from typing import Optional


class PoolResolver:
    """Resolves IP addresses to pool labels using CIDR ranges from pools.json.

    Reads a JSON file containing a list of {"cidr": "...", "label": "..."} objects.
    Performs longest-prefix match to return the most specific label for an IP.
    Degrades gracefully when the file is missing, unreadable, or malformed.
    """

    def __init__(self, pools_file: Optional[Path] = None, logger=None):
        self._pools = []  # list of (network, label)

        if pools_file is None:
            return

        try:
            with open(pools_file) as f:
                entries = json.load(f)
            for e in entries:
                cidr = e.get('cidr', '')
                label = e.get('label', '')
                if not cidr or not label:
                    continue
                try:
                    self._pools.append((ipaddress.ip_network(cidr, strict=False), label))
                except ValueError:
                    if logger:
                        logger.log_error(f"PoolResolver: invalid CIDR '{cidr}', skipping")
            if logger:
                logger.log_debug(f"PoolResolver: loaded {len(self._pools)} pool entries from {pools_file}")
        except FileNotFoundError:
            if logger:
                logger.log_debug(f"PoolResolver: pools file not found at {pools_file}, pool labels disabled")
        except Exception as ex:
            if logger:
                logger.log_error(f"PoolResolver: failed to load pools file: {ex}")

    def get_label(self, ip: str) -> str:
        """Return pool label for the given IP using longest-prefix match.

        Returns '' if no match or pools file was not loaded.
        """
        if not self._pools:
            return ''
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return ''
        best, best_len = '', -1
        for net, label in self._pools:
            if addr in net and net.prefixlen > best_len:
                best, best_len = label, net.prefixlen
        return best
