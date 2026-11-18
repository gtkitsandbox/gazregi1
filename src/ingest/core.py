"""Shared transport, provenance and dataset-writing helpers for ingestion."""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from html.parser import HTMLParser

from src.content.models import (
    CuratedRecord,
    NoticeDetail,
    OrganisationEntity,
    RecordSource,
    RegulationDetail,
    SourceDocumentSnapshot,
    SourceRegistryEntry,
    TenderDetail,
    normalise_name,
    normalise_text,
    slugify_id,
)

USER_AGENT = (
    "GazetteRegistry/1.0 (public-records research; contact via gazetteregistry.com)"
)
DEFAULT_TIMEOUT = 45
POLITE_DELAY = 0.6
_RETRIEVED = date.today()


class FetchError(RuntimeError):
    pass


def fetch(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 2,
    accept: str | None = None,
) -> tuple[bytes, str]:
    """Fetch an official source politely and return (body, content-type)."""
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept or "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en;q=0.9,*;q=0.5",
    }
    if headers:
        request_headers.update(headers)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(1.5 * attempt)
        request = urllib.request.Request(
            url, data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "")
                time.sleep(POLITE_DELAY)
                return body, content_type
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
    raise FetchError(f"{method} {url} failed: {last_error}")


def fetch_text(url: str, **kwargs: Any) -> str:
    body, _ = fetch(url, **kwargs)
    return decode(body)


def decode(body: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "iso-8859-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "iframe", "form"}
    BLOCK = {
        "p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4",
        "h5", "h6", "table", "section", "article", "header", "footer", "dd", "dt",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [normalise_text(line) for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    return parser.text()


def strip_tags(markup: str) -> str:
    return normalise_text(html.unescape(re.sub(r"<[^>]+>", " ", markup)))


def absolute(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, html.unescape(href.strip()))


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\([^)]*\)", "", str(value)).strip().replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z",
        "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d",
        "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
        "%A, %d %B %Y %I:%M %p", "%A, %d %B %Y", "%d %B %Y %I:%M %p",
        "%d %b %Y %I:%M %p", "%Y%m%d", "%d %B %Y, %H:%M",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    match = re.search(r"(20\d{2}|19\d{2})[-/.](\d{2})[-/.](\d{2})", text)
    if match:
        y, m, d = match.groups()
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None
    match = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})", text)
    if match:
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(" ".join(match.groups()), fmt).date()
            except ValueError:
                continue
    return None


def parse_time(value: Any) -> str | None:
    if not value:
        return None
    match = re.search(r"\b([01]\d|2[0-3]):([0-5]\d)", str(value))
    return f"{match.group(1)}:{match.group(2)}" if match else None


CONTACT_MARKERS = (
    "contact person",
    "contact name",
    "contact details",
    "designation",
    "e-mail",
    "email",
    "telephone",
    "phone",
    "mobile",
    "fax",
)
CONTACT_LINE = re.compile(
    r"^\s*(?:contact person|contact name|contact details|designation|e-?mail(?: address)?|"
    r"telephone|phone(?: no\.?)?|mobile(?: no\.?| number)?|fax(?: no\.?)?)\s*[:：]",
    re.I,
)
CONTACT_VALUE = re.compile(
    r"\b(contact person|contact name|designation|e-?mail(?: address)?|telephone|"
    r"phone(?: no\.?)?|mobile(?: no\.?| number)?|fax(?: no\.?)?)\b\s*[:：]\s*[^\n|;]{2,120}",
    re.I,
)


def scrub_personal(text: str) -> str:
    """Remove contact-person fields and redact contact values from a snapshot.

    Short lines that are only a contact label/value are dropped; larger
    passages are retained with the contact value redacted so the surrounding
    publication text and any verbatim excerpt remain intact.
    """
    lines: list[str] = []
    for line in text.splitlines():
        if len(line) <= 200 and CONTACT_LINE.match(line):
            continue
        line = CONTACT_VALUE.sub(lambda m: f"{m.group(1)}: [contact removed]", line)
        line = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[contact removed]", line)
        lines.append(line)
    return "\n".join(lines)


def truncate(text: str, limit: int) -> str:
    text = normalise_text(text)
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip()


@dataclass
class DocumentDraft:
    source_id: str
    official_url: str
    content_type: str
    language: str
    title: str
    text: str
    publisher: str | None = None
    publication_date: date | None = None
    source_sha256: str = ""
    source_bytes: int = 0


@dataclass
class RecordDraft:
    record_type: str
    title: str
    publication_date: date
    document_id: str
    source_id: str
    official_url: str
    excerpt: str
    source_sha256: str
    title_slug: str = ""
    record_year: int | None = None
    language: str | None = None
    summary: str | None = None
    location: str | None = None
    keywords: list[str] = field(default_factory=list)
    organisation_name: str | None = None
    organisation_type: str = "government_body"
    sector: str = "other"
    tender: dict[str, Any] | None = None
    notice: dict[str, Any] | None = None
    regulation: dict[str, Any] | None = None
    issuing_organisation_name: str | None = None


def _ml(value: Any) -> dict[str, Any]:
    """Serialise a pydantic model or dataclass-like object to JSON-safe data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(type(value))


class Dataset:
    """Read, extend and rewrite one country's ingestion output."""

    def __init__(self, data_root: Path, country_code: str) -> None:
        self.country = country_code.upper()
        self.root = data_root / self.country.lower()
        self.documents_path = self.root / "sources" / "documents.ndjson"
        self.registry_path = self.root / "sources" / "registry.ndjson"
        self.records_path = self.root / "records" / "records.ndjson"
        self.orgs_path = self.root / "entities" / "organisations.ndjson"
        self.documents: dict[str, SourceDocumentSnapshot] = {}
        self.registry: dict[str, SourceRegistryEntry] = {}
        self.records: dict[str, CuratedRecord] = {}
        self.orgs: dict[str, OrganisationEntity] = {}
        self.new_records = 0
        self.skipped = 0
        for path, store, model in (
            (self.documents_path, self.documents, SourceDocumentSnapshot),
            (self.registry_path, self.registry, SourceRegistryEntry),
            (self.records_path, self.records, CuratedRecord),
            (self.orgs_path, self.orgs, OrganisationEntity),
        ):
            for row in self._read_ndjson(path, model):
                key = getattr(row, "document_id", None) or getattr(row, "source_id", None) or getattr(row, "uid", None) or getattr(row, "organisation_id", "")
                store[key] = row

    @staticmethod
    def _read_ndjson(path: Path, model: Any) -> list[Any]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(model.model_validate_json(line))
        return rows

    def existing_document(self, official_url: str, title: str | None = None) -> SourceDocumentSnapshot | None:
        for document in self.documents.values():
            if str(document.official_url) == official_url and (
                title is None or document.title.casefold() == title.casefold()
            ):
                return document
        return None

    def add_document(self, draft: DocumentDraft, raw_body: bytes | None = None) -> str:
        existing = self.existing_document(draft.official_url, draft.title)
        if existing is not None:
            return existing.document_id
        number = len(self.documents) + 1
        document_id = f"DOC-{self.country}-{number:04d}"
        while document_id in self.documents:
            number += 1
            document_id = f"DOC-{self.country}-{number:04d}"
        document = SourceDocumentSnapshot(
            document_id=document_id,
            country_code=self.country,
            source_id=draft.source_id,
            official_url=draft.official_url,
            retrieved_at=_RETRIEVED,
            content_type=draft.content_type,
            language=draft.language,
            title=draft.title,
            publisher=draft.publisher,
            publication_date=draft.publication_date,
            source_sha256=draft.source_sha256 or sha256(raw_body or b""),
            source_bytes=draft.source_bytes or len(raw_body or b""),
            text=scrub_personal(draft.text),
        )
        self.documents[document_id] = document
        return document_id

    def _uid(self, year: int, category: str, slug: str | None = None) -> str:
        prefix = f"{self.country}-{year}-"
        taken = {
            record.uid
            for record in self.records.values()
            if record.uid.startswith(prefix)
        }
        for number in range(1, 100000):
            uid = f"{prefix}{category}-{number:03d}"
            if uid not in taken:
                return uid
        raise RuntimeError("UID space exhausted")

    def _org(self, name: str, org_type: str, document: SourceDocumentSnapshot) -> str:
        slug = slugify_id(name)[:60].strip("-") or "unknown-organisation"
        org_id = f"org:{self.country.lower()}:{slug}"
        if org_id not in self.orgs:
            self.orgs[org_id] = OrganisationEntity(
                organisation_id=org_id,
                country_code=self.country,
                name=normalise_text(name),
                type=org_type,  # type: ignore[arg-type]
                identity_status="operator_verified",
                verified_at=_RETRIEVED,
                basis=(
                    f"Named as the issuing or buying organisation in official source "
                    f"{document.official_url} retrieved {_RETRIEVED.isoformat()}."
                ),
            )
        return org_id

    def add_record(self, draft: RecordDraft) -> CuratedRecord | None:
        document = self.documents.get(draft.document_id)
        if document is None:
            raise ValueError(f"unknown document {draft.document_id}")
        excerpt = normalise_text(draft.excerpt)
        if excerpt and excerpt not in normalise_text(document.text):
            raise ValueError(f"excerpt not present in document {draft.document_id}: {excerpt[:80]}")
        if not excerpt or len(excerpt) < 20:
            excerpt = truncate(document.text, 400)

        for record in self.records.values():
            if record.title.casefold() == draft.title.casefold() and record.record_type == draft.record_type:
                self.skipped += 1
                return None

        year = draft.record_year or (draft.publication_date or document.publication_date or _RETRIEVED).year
        category = {
            "tender": "TEND",
            "public_notice": "NOTC",
            "regulation": "REGL",
        }.get(draft.record_type, "APPT")
        uid = self._uid(year, category)

        org_id = None
        if draft.organisation_name:
            org_id = self._org(draft.organisation_name, draft.organisation_type, document)

        tender = None
        if draft.tender is not None:
            payload = dict(draft.tender)
            payload.setdefault("issuer_organisation_id", org_id)
            tender = TenderDetail(**payload)
        notice = NoticeDetail(**draft.notice) if draft.notice is not None else None
        regulation = RegulationDetail(**draft.regulation) if draft.regulation is not None else None

        record = CuratedRecord(
            uid=uid,
            record_type=draft.record_type,  # type: ignore[arg-type]
            title=normalise_text(draft.title)[:300],
            summary=draft.summary,
            issue_id=None,
            publication_date=draft.publication_date,
            language=draft.language or document.language,
            issuing_organisation_name=draft.issuing_organisation_name,
            organisation_ids=[org_id] if org_id else [],
            location=draft.location,
            keywords=draft.keywords[:12],
            tender=tender,
            notice=notice,
            regulation=regulation,
            source=RecordSource(
                kind="json" if "json" in document.content_type else ("csv" if "csv" in document.content_type else ("xml" if "xml" in document.content_type else "html")),
                document_id=document.document_id,
                excerpt=excerpt[:1200],
                official_url=draft.official_url,
                sha256=document.source_sha256,
                retrieved_at=document.retrieved_at,
            ),
        )
        self.records[uid] = record
        self.new_records += 1
        return record

    def set_registry(self, entry: SourceRegistryEntry) -> None:
        self.registry[entry.source_id] = entry

    def save(self) -> None:
        self.documents_path.parent.mkdir(parents=True, exist_ok=True)
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        self.orgs_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_ndjson(self.documents_path, sorted(self.documents.values(), key=lambda d: d.document_id))
        self._write_ndjson(self.records_path, sorted(self.records.values(), key=lambda r: r.uid))
        self._write_ndjson(self.orgs_path, sorted(self.orgs.values(), key=lambda o: o.organisation_id))
        self._write_ndjson(self.registry_path, sorted(self.registry.values(), key=lambda s: s.source_id))

    @staticmethod
    def _write_ndjson(path: Path, rows: Iterable[Any]) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(_ml(row), ensure_ascii=False, sort_keys=True) + "\n")
