"""Regression tests for date-derived opportunity status."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from content.build import _closing_state, _effective_status  # noqa: E402


class ClosingStateTests(unittest.TestCase):
    def test_missing_closing_date_is_unknown(self) -> None:
        self.assertEqual(_closing_state(None), "unknown")

    def test_expired_closing_date_is_closed(self) -> None:
        self.assertEqual(_closing_state(date.today() - timedelta(days=1)), "closed")

    def test_future_closing_date_is_open(self) -> None:
        self.assertEqual(_closing_state(date.today() + timedelta(days=1)), "open")


class EffectiveStatusTests(unittest.TestCase):
    def test_source_open_cannot_override_past_closing_date(self) -> None:
        self.assertEqual(
            _effective_status("open", date.today() - timedelta(days=1)), "closed"
        )

    def test_forecast_cannot_override_past_closing_date(self) -> None:
        self.assertEqual(
            _effective_status("forecast", date.today() - timedelta(days=1)), "closed"
        )

    def test_source_open_with_future_closing_date_stays_open(self) -> None:
        self.assertEqual(
            _effective_status("open", date.today() + timedelta(days=1)), "open"
        )

    def test_open_without_closing_date_is_unknown(self) -> None:
        self.assertEqual(_effective_status("open", None), "unknown")

    def test_terminal_source_statuses_are_preserved(self) -> None:
        for status in ("awarded", "cancelled", "closed"):
            with self.subTest(status=status):
                self.assertEqual(
                    _effective_status(status, date.today() + timedelta(days=1)), status
                )


if __name__ == "__main__":
    unittest.main()
