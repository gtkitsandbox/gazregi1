"""Regression tests for historical and scanned PDF intake."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from extract_pdf import extract_issue  # noqa: E402


def make_pdf(path: Path, lines: list[str]) -> None:
    document = pymupdf.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 18), line)
    document.save(path)
    document.close()


class HistoricalPdfTests(unittest.TestCase):
    def test_regular_issue_from_standard_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "Gazette-1999-01-02-E.pdf"
            make_pdf(
                pdf,
                [
                    "No. 1234",
                    "GAZETTE OF THE DEMOCRATIC SOCIALIST REPUBLIC",
                    "7",
                    "Appointment notice",
                ],
            )
            output = extract_issue(pdf, root / "data", country_code="lk")
            issue = json.loads((output / "issue.json").read_text(encoding="utf-8"))
            self.assertEqual(issue["issue_id"], "LK-1999-1234")
            self.assertEqual(issue["gazette_type"], "regular")
            self.assertEqual(issue["publication_date"], "1999-01-02")
            self.assertTrue((output / "pages.ndjson").exists())

    def test_explicit_metadata_for_nonstandard_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "old-supplement.pdf"
            make_pdf(
                pdf,
                [
                    "29131.",
                    "3693",
                    "FOURTH SUPPLEMENT TO THE LONDON GAZETTE",
                    "War Office, 15th April, 1915.",
                ],
            )
            output = extract_issue(
                pdf,
                root / "data",
                country_code="gb",
                publication_date="1915-04-13",
                edition="S",
                gazette_type="supplement",
                language="en",
            )
            issue = json.loads((output / "issue.json").read_text(encoding="utf-8"))
            self.assertEqual(issue["issue_id"], "GB-1915-29131")
            self.assertEqual(issue["gazette_no"], "29131")
            self.assertEqual(issue["gazette_type"], "supplement")
            self.assertEqual(issue["edition"], "S")
            page = json.loads((output / "pages.ndjson").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(page["source"]["language"], "en")

    def test_scanned_pdf_fails_instead_of_silently_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "Gazette-1999-01-02-E.pdf"
            make_pdf(pdf, [])
            with self.assertRaisesRegex(ValueError, "OCR is not enabled"):
                extract_issue(
                    pdf, root / "data", country_code="lk", gazette_number="1234"
                )


if __name__ == "__main__":
    unittest.main()
