"""Tests for FS3 file log collector."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = Path(__file__).resolve().parents[1] / "src"
for p in (str(ROOT), str(AGENT_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from log_collector import (  # noqa: E402
    CombinedLogCollector,
    FileLogCollector,
    JournaldCollector,
    WinEventLogCollector,
    journald_record_to_event,
    parse_line,
    winevt_record_to_event,
)


def test_parse_json_and_raw():
    js = parse_line('{"level":"error","message":"boom"}', "json")
    assert js["parsed"] is True
    assert js["severity"] == "error"
    assert js["message"] == "boom"
    raw = parse_line("hello", "raw")
    assert raw["parsed"] is False
    assert raw["message"] == "hello"


def test_file_tail_offset_and_filter(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("keep me\ndrop secret\nkeep again\n", encoding="utf-8")
    collector = FileLogCollector(
        patterns=[str(log)],
        offset_path=tmp_path / "off.json",
        parser="raw",
        exclude_regex="secret",
        alert_patterns=["keep again"],
    )
    events, alerts = collector.collect()
    messages = [e["message"] for e in events]
    assert "keep me" in messages
    assert "keep again" in messages
    assert not any("secret" in m for m in messages)
    assert len(alerts) == 1

    events2, _ = collector.collect()
    assert events2 == []


def test_rate_limit_spills(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("aaaaaaaaaa\nbbbbbbbbbb\n", encoding="utf-8")
    spill = tmp_path / "spill.log"
    collector = FileLogCollector(
        patterns=[str(log)],
        offset_path=tmp_path / "off.json",
        max_bytes_per_min=12,
        spill_path=spill,
    )
    events, _ = collector.collect()
    assert collector.rate_limited is True
    assert spill.exists()
    assert len(events) < 2


def test_journald_cursor_no_backfill(tmp_path):
    calls = []

    def reader(cursor, units, max_entries):
        calls.append((cursor, tuple(units), max_entries))
        if cursor is None:
            return [{"MESSAGE": "old", "PRIORITY": "3", "__CURSOR": "c1"}], "c1"
        return [
            {
                "MESSAGE": "nginx fail",
                "PRIORITY": "3",
                "_SYSTEMD_UNIT": "nginx.service",
                "__CURSOR": "c2",
                "__REALTIME_TIMESTAMP": "1755000000000000",
            }
        ], "c2"

    collector = JournaldCollector(
        state_path=tmp_path / "off.json",
        units=["nginx.service"],
        reader=reader,
        alert_patterns=["fail"],
    )
    events, alerts = collector.collect()
    assert events == []
    assert alerts == []
    assert calls[0][0] is None

    events, alerts = collector.collect()
    assert len(events) == 1
    assert events[0]["source"] == "journald"
    assert events[0]["channel"] == "nginx.service"
    assert events[0]["severity"] == "error"
    assert alerts[0]["message"] == "nginx fail"
    assert calls[1][0] == "c1"


def test_winevt_bookmarks_and_channels(tmp_path):
    bookmarks = {"System": 10, "Application": 3}

    def bookmarker(channel):
        return bookmarks[channel]

    def reader(channel, after_id, limit):
        if channel == "System":
            return [
                {
                    "RecordId": 11,
                    "TimeCreated": "2026-08-13T10:00:00+00:00",
                    "Level": 2,
                    "ProviderName": "Service Control Manager",
                    "Id": 7031,
                    "Message": "service crashed",
                    "Channel": "System",
                }
            ]
        return []

    collector = WinEventLogCollector(
        state_path=tmp_path / "off.json",
        channels=["System", "Application"],
        reader=reader,
        bookmarker=bookmarker,
    )
    events, _ = collector.collect()
    assert events == []  # first pass seeds bookmarks

    events, _ = collector.collect()
    assert len(events) == 1
    assert events[0]["source"] == "winevt"
    assert events[0]["channel"] == "System"
    assert events[0]["severity"] == "error"
    assert "service crashed" in events[0]["message"]

    events2, _ = collector.collect()
    # same fake reader returns RecordId 11 again; bookmark is now 11 so still returned
    # unless reader honors after_id — simulate that
    assert events2[0]["record_id"] == 11


def test_winevt_reader_honors_bookmark(tmp_path):
    def bookmarker(_channel):
        return 5

    def reader(channel, after_id, limit):
        assert after_id >= 5
        if after_id >= 12:
            return []
        return [
            {
                "RecordId": 12,
                "TimeCreated": "2026-08-13T11:00:00+00:00",
                "Level": 3,
                "ProviderName": "Disk",
                "Id": 7,
                "Message": "disk warning",
                "Channel": channel,
            }
        ]

    collector = WinEventLogCollector(
        state_path=tmp_path / "off.json",
        channels=["System"],
        reader=reader,
        bookmarker=bookmarker,
    )
    collector.collect()
    events, _ = collector.collect()
    assert events[0]["severity"] == "warning"
    events2, _ = collector.collect()
    assert events2 == []


def test_combined_from_config_files_only(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("hello\n", encoding="utf-8")
    collector = CombinedLogCollector.from_config(
        {
            "enabled": True,
            "files": [str(log)],
            "offset_path": str(tmp_path / "off.json"),
            "journald": {"enabled": False},
            "winevt": {"enabled": False},
        }
    )
    assert collector is not None
    events, _ = collector.collect()
    assert events[0]["source"] == "file"
    assert events[0]["message"] == "hello"


def test_journald_and_winevt_event_shapes():
    jd = journald_record_to_event({"MESSAGE": "x", "PRIORITY": "4", "_SYSTEMD_UNIT": "sshd.service"})
    assert jd["severity"] == "warning"
    assert jd["source"] == "journald"
    win = winevt_record_to_event({"Level": 1, "Message": "halt", "Channel": "System", "ProviderName": "Kernel", "Id": 41})
    assert win["severity"] == "critical"
    assert win["source"] == "winevt"
