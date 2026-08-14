"""Regression tests for the DNS block list summary delta.

These cover the reporting bug where a run announced "Delisted IPs 13" while
the headline "153 IPs listed" did not move: the delisted figure was counted
from a previous-run snapshot that had lost its DBL markers, so domains coming
off a DBL were reported as IPs coming off an RBL.
"""

import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dnscheck import DNSCheck, classify_entities  # noqa: E402


HEADER = [
    "timestamp", "source_ip", "check_type", "target", "target_source",
    "server", "obm_server", "response", "txt_context",
]


def _write_report(path, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow(row)


def _rbl_row(ip, server="zen.spamhaus.org"):
    return ["13 Aug 2026 14:32:44", ip, "IP", ip, "ip", server, "oxygen", "127.0.0.3", ""]


def _dbl_row(ip, domain, source="apex", server="dbl.spamhaus.org"):
    return [
        "13 Aug 2026 14:32:44", ip, source.upper(), domain, source,
        server, "oxygen", "127.0.1.2", "",
    ]


@pytest.fixture
def checker(tmp_path, monkeypatch):
    import config as config_module

    monkeypatch.setattr(config_module.config, "report_dir", tmp_path, raising=False)
    instance = DNSCheck.__new__(DNSCheck)
    instance.logger = MagicMock()
    instance.webhook_client = MagicMock()
    instance.webhook_client.send_notification.return_value = (True, [])
    instance.webhook_client.upload_csv_to_slack.return_value = (True, None)
    return instance


class TestPreviousResultLabels:
    def test_dbl_rows_keep_their_domain_marker(self, checker, tmp_path):
        _write_report(tmp_path / "report_1.csv", [
            _rbl_row("91.103.141.3"),
            _dbl_row("91.103.141.3", "simpliemail.com"),
            _dbl_row("91.103.141.223", "simpliemail.com"),
            _dbl_row("91.103.141.223", "a141-223.simpliemail.com", source="ptr"),
        ])

        previous = checker._load_previous_results()

        assert previous["91.103.141.3"] == [
            "zen.spamhaus.org",
            "dbl.spamhaus.org [apex:simpliemail.com]",
        ]
        # The IP with no RBL row must not look like an RBL listing.
        assert previous["91.103.141.223"] == [
            "dbl.spamhaus.org [apex:simpliemail.com]",
            "dbl.spamhaus.org [ptr:a141-223.simpliemail.com]",
        ]

    def test_labels_round_trip_through_the_csv(self, checker, tmp_path):
        """A loaded report must equal the in-memory dict that produced it."""
        _write_report(tmp_path / "report_1.csv", [
            _rbl_row("91.103.141.3"),
            _dbl_row("91.103.141.3", "simpliemail.com"),
        ])
        in_memory = {
            "91.103.141.3": [
                "zen.spamhaus.org",
                "dbl.spamhaus.org [apex:simpliemail.com]",
            ]
        }
        assert checker._load_previous_results() == in_memory

    def test_current_run_is_excluded(self, checker, tmp_path):
        old = tmp_path / "report_1.csv"
        new = tmp_path / "report_2.csv"
        _write_report(old, [_rbl_row("1.1.1.1")])
        _write_report(new, [_rbl_row("2.2.2.2")])
        import os
        os.utime(new, (2_000_000_000, 2_000_000_000))

        assert set(checker._load_previous_results(new)) == {"1.1.1.1"}


class TestWriterReaderRoundTrip:
    """The CSV must be a lossless carrier for the labels the delta compares."""

    def test_write_report_then_reload_reproduces_listed_ips(self, tmp_path, monkeypatch):
        import config as config_module
        from threading import Lock

        monkeypatch.setattr(config_module.config, "report_dir", tmp_path, raising=False)
        monkeypatch.setattr(
            config_module.config, "get_address_groups", lambda: {"oxygen": ["91.103.141.0/24"]},
            raising=False,
        )

        checker = DNSCheck.__new__(DNSCheck)
        checker.logger = MagicMock()
        checker.lock = Lock()
        checker.listed_ips = {}
        checker.report_file_handler = None
        checker.csv_writer = None
        checker.current_report_path = None

        results = [
            ("91.103.141.3", "zen.spamhaus.org", True, "127.0.0.3"),
            ("91.103.141.3", "simpliemail.com", "apex", "dbl.spamhaus.org", True, "127.0.1.2", ""),
            ("91.103.141.223", "a141-223.simpliemail.com", "ptr",
             "dbl.spamhaus.org", True, "127.0.1.2", ""),
        ]
        for result in results:
            checker._process_check_result(result)
        checker.report_file_handler.close()

        written = dict(checker.listed_ips)
        reloaded = checker._load_previous_results()

        assert reloaded == written
        # And the reload preserves the distinction the summary depends on.
        ips, domains, dbl_ips = classify_entities(reloaded)
        assert ips == {"91.103.141.3"}
        assert domains == {"simpliemail.com", "a141-223.simpliemail.com"}
        assert dbl_ips == {"91.103.141.3", "91.103.141.223"}


class TestClassifyEntities:
    def test_dbl_only_ip_is_not_a_listed_ip(self):
        ips, domains, dbl_ips = classify_entities({
            "91.103.141.223": ["dbl.spamhaus.org [apex:simpliemail.com]"],
        })
        assert ips == set()
        assert domains == {"simpliemail.com"}
        assert dbl_ips == {"91.103.141.223"}

    def test_populations_are_independent(self):
        ips, domains, dbl_ips = classify_entities({
            "1.1.1.1": ["zen.spamhaus.org"],
            "2.2.2.2": ["dbl.spamhaus.org [ptr:mail.example.com]"],
            "3.3.3.3": ["zen.spamhaus.org", "dbl.spamhaus.org [apex:example.com]"],
        })
        assert ips == {"1.1.1.1", "3.3.3.3"}
        assert domains == {"mail.example.com", "example.com"}
        assert dbl_ips == {"2.2.2.2", "3.3.3.3"}


class TestCategorizeResults:
    def test_partial_delisting_is_detected(self, checker):
        previous = {"1.1.1.1": ["zen.spamhaus.org", "b.barracudacentral.org"]}
        current = {"1.1.1.1": ["zen.spamhaus.org"]}

        newly, still, delisted = checker._categorize_results(current, previous)

        assert newly == {}
        assert still == {"1.1.1.1": ["zen.spamhaus.org"]}
        assert delisted == {"1.1.1.1": ["b.barracudacentral.org"]}

    def test_new_listing_on_an_already_listed_ip_is_detected(self, checker):
        previous = {"1.1.1.1": ["zen.spamhaus.org"]}
        current = {"1.1.1.1": ["zen.spamhaus.org", "b.barracudacentral.org"]}

        newly, _, delisted = checker._categorize_results(current, previous)

        assert newly == {"1.1.1.1": ["b.barracudacentral.org"]}
        assert delisted == {}


class TestPersistenceGateInteraction:
    def test_held_sighting_does_not_become_a_phantom_delisting(self, checker):
        """A DBL sighting held back last run was never announced as listed,
        so it must not be announced as delisted this run."""
        previous_csv = {
            "1.1.1.1": ["zen.spamhaus.org"],
            "2.2.2.2": ["dbl.spamhaus.org [apex:example.com]"],
        }
        pending = {("2.2.2.2", "dbl.spamhaus.org")}

        alerted = checker._strip_held_sightings(previous_csv, pending)

        assert alerted == {"1.1.1.1": ["zen.spamhaus.org"]}

    def test_flatten_pairs_strips_the_domain_suffix(self):
        pairs = DNSCheck._flatten_previous_pairs({
            "1.1.1.1": ["zen.spamhaus.org", "dbl.spamhaus.org [apex:example.com]"],
        })
        assert pairs == {
            ("1.1.1.1", "zen.spamhaus.org"),
            ("1.1.1.1", "dbl.spamhaus.org"),
        }


class TestSummaryArithmetic:
    """previous + new - delisted == total, for both populations."""

    def _summary(self, checker, previous, current):
        newly, still, delisted = checker._categorize_results(current, previous)
        checker._get_address_group = lambda ip: "oxygen"
        checker._send_categorized_notifications(
            newly=newly, still=still, delisted=delisted, previous=previous,
        )
        payload = checker.webhook_client.send_notification.call_args[0][0]
        return payload["summary"]

    def test_the_reported_incident_shape(self, checker):
        """153 RBL-listed IPs unchanged while 13 DBL-only IPs drop out.

        The old code reported this as 'Delisted IPs 13' against an unmoved
        total of 153. It must now be attributed to the domain population.
        """
        rbl_ips = {f"91.103.141.{n}": ["zen.spamhaus.org"] for n in range(2, 155)}
        dbl_only = {
            f"91.103.141.{n}": [f"dbl.spamhaus.org [ptr:a141-{n}.simpliemail.com]"]
            for n in (223, 224, 225, 226, 230, 231, 234, 239, 240, 245, 248, 251, 254)
        }
        previous = {**rbl_ips, **dbl_only}
        current = dict(rbl_ips)

        summary = self._summary(checker, previous, current)

        assert len(rbl_ips) == 153
        assert summary["total_listed_ips"] == 153
        assert summary["previous_listed_ips"] == 153
        assert summary["delisted_ips"] == []          # was 13 before the fix
        assert summary["newly_listed_ips"] == []
        assert len(summary["delisted_domains"]) == 13  # correctly attributed
        assert len(summary["cleared_dbl_affected_ips"]) == 13

    def test_ip_arithmetic_closes(self, checker):
        previous = {"1.1.1.1": ["zen.spamhaus.org"], "2.2.2.2": ["zen.spamhaus.org"]}
        current = {"2.2.2.2": ["zen.spamhaus.org"], "3.3.3.3": ["zen.spamhaus.org"]}

        s = self._summary(checker, previous, current)

        assert s["total_listed_ips"] == (
            s["previous_listed_ips"] + len(s["newly_listed_ips"]) - len(s["delisted_ips"])
        )
        assert s["newly_listed_ips"] == ["3.3.3.3"]
        assert s["delisted_ips"] == ["1.1.1.1"]

    def test_domain_arithmetic_closes(self, checker):
        previous = {
            "1.1.1.1": ["dbl.spamhaus.org [apex:a.com]"],
            "2.2.2.2": ["dbl.spamhaus.org [apex:b.com]"],
        }
        current = {
            "2.2.2.2": ["dbl.spamhaus.org [apex:b.com]"],
            "3.3.3.3": ["dbl.spamhaus.org [apex:c.com]"],
        }

        s = self._summary(checker, previous, current)

        assert s["total_listed_domains"] == (
            s["previous_listed_domains"]
            + len(s["newly_listed_domains"])
            - len(s["delisted_domains"])
        )
        assert s["newly_listed_domains"] == ["c.com"]
        assert s["delisted_domains"] == ["a.com"]
        assert s["total_listed_ips"] == 0

    def test_no_arithmetic_error_is_logged(self, checker):
        previous = {"1.1.1.1": ["zen.spamhaus.org", "dbl.spamhaus.org [apex:a.com]"]}
        current = {"2.2.2.2": ["dbl.spamhaus.org [ptr:m.b.com]"]}

        self._summary(checker, previous, current)

        assert checker.logger.log_error.call_count == 0

    def test_server_breakdown_matches_the_headline(self, checker):
        current = {
            "91.103.141.3": ["zen.spamhaus.org"],
            "91.103.141.4": ["zen.spamhaus.org", "dbl.spamhaus.org [apex:x.com]"],
            "91.103.141.5": ["dbl.spamhaus.org [apex:x.com]"],
        }
        s = self._summary(checker, {}, current)
        oxygen = s["affected_servers"][0]

        assert oxygen["server"] == "oxygen"
        assert oxygen["listed_ips"] == s["total_listed_ips"] == 2
        assert oxygen["listed_domains"] == s["total_listed_domains"] == 1
        assert oxygen["dbl_affected_ips"] == s["dbl_affected_ips"] == 2
