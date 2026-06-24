"""Streaming replay clock — anchor advances with wall-clock (no DB)."""

import time
from datetime import datetime, timezone

from greenflow import replayclock as rc


def test_streaming_anchor_advances_and_stays_in_range():
    base = datetime(2025, 7, 30, 14, 0, tzinfo=timezone.utc)
    try:
        rc._stream = {
            "started": datetime.now(timezone.utc),
            "speed": 3600.0,
            "lo": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "hi": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "base": base,
        }
        a1 = rc.anchor()
        time.sleep(0.05)
        a2 = rc.anchor()
        assert a2 > a1                                  # clock advances
        assert rc._stream["lo"] <= a1 <= rc._stream["hi"]  # stays within data range
        assert a1 >= base                               # starts at/after the demo time
    finally:
        rc._stream = None


def test_streaming_loops_within_window():
    base = datetime(2025, 12, 31, 23, 0, tzinfo=timezone.utc)
    try:
        # tiny window + huge speed -> elapsed wraps past `hi` back near `lo`
        rc._stream = {
            "started": datetime.now(timezone.utc),
            "speed": 1e6,
            "lo": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "hi": datetime(2025, 1, 2, tzinfo=timezone.utc),
            "base": base if base <= datetime(2025, 1, 2, tzinfo=timezone.utc)
            else datetime(2025, 1, 1, 12, tzinfo=timezone.utc),
        }
        a = rc.anchor()
        assert rc._stream["lo"] <= a <= rc._stream["hi"]  # never escapes the window
    finally:
        rc._stream = None
