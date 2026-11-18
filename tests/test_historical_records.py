"""Regression tests for genuine historical Gazette records."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from content.loader import load_site  # noqa: E402


class HistoricalRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.site = load_site(
            data_root=ROOT / "data",
            config_path=ROOT / "config" / "site.json",
            raw_root=ROOT / "raw",
            preview=False,
            site_url="https://gazetteregistry.com",
        )

    def test_historical_person_has_gazette_provenance(self) -> None:
        person = self.site.person_for("person:gb:havelock-hudson")
        records = self.site.records_for_person(person.person_id)
        self.assertEqual(len(records), 2)
        self.assertEqual(
            [record.publication_date.isoformat() for record in records],
            ["1915-04-13", "1914-12-08"],
        )
        promotion = records[0]
        self.assertEqual(promotion.record_type, "promotion")
        self.assertEqual(promotion.issue_id, "GB-1915-29131")
        self.assertEqual(promotion.source.pdf_page, 1)
        self.assertEqual(promotion.source.checksum_scope, "original_source")
        self.assertEqual(promotion.people[0].position_kind, "promotion")
        appointment = records[1]
        self.assertEqual(appointment.record_type, "appointment")
        self.assertEqual(appointment.issue_id, "GB-1914-29002")

    def test_historical_name_variant_is_verified(self) -> None:
        variants = self.site.verified_variants_for("person:gb:havelock-hudson")
        self.assertEqual([variant.name for variant in variants], ["Havelock Hudson, C.B., C.I.E."])

    def test_historical_record_is_not_published_as_current(self) -> None:
        record = self.site.records_for_person("person:gb:ian-m-smith")[0]
        self.assertEqual(record.record_type, "appointment")
        self.assertEqual(record.issue_id, "GB-1915-29131")
        self.assertEqual(record.source.checksum_scope, "original_source")


if __name__ == "__main__":
    unittest.main()
