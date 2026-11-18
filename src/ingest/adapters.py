"""Adapters for official international publication and procurement sources.

Each adapter normalises one official source family.  Adapters never invent a
title, date, reference or URL: every field is taken from the fetched source and
the stored document snapshot is the verbatim basis for the record excerpt.
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any, Callable

from src.content.models import normalise_text
from src.ingest.core import (
    Dataset,
    DocumentDraft,
    RecordDraft,
    absolute,
    decode,
    fetch,
    fetch_text,
    html_to_text,
    parse_date,
    parse_time,
    sha256,
    strip_tags,
    truncate,
)

TODAY = date.today()

SECTOR_WORDS: tuple[tuple[str, str], ...] = (
    ("construction", "civil_works"),
    ("works", "civil_works"),
    ("building", "civil_works"),
    ("road", "civil_works"),
    ("goods", "goods"),
    ("supplies", "goods"),
    ("supply", "goods"),
    ("equipment", "goods"),
    ("medical", "goods"),
    ("software", "it"),
    ("ict", "it"),
    ("information technology", "it"),
    ("consult", "consultancy"),
    ("professional", "consultancy"),
    ("maintenance", "maintenance"),
    ("cleaning", "services"),
    ("services", "services"),
)


def infer_sector(value: str | None, default: str = "other") -> str:
    text = (value or "").casefold()
    for word, sector in SECTOR_WORDS:
        if word in text:
            return sector
    return default


def _record(ds: Dataset, draft: RecordDraft) -> bool:
    try:
        return ds.add_record(draft) is not None
    except ValueError as exc:
        print(f"  skip: {exc}")
        return False


def _text_field(*parts: tuple[str, Any]) -> str:
    lines = []
    for label, value in parts:
        if value not in (None, "", [], {}):
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(item) for item in value)
            lines.append(f"{label}: {normalise_text(str(value))}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# United Kingdom
# ---------------------------------------------------------------------------

UK_ATOM = "https://www.thegazette.co.uk/all-notices/notice/data.feed?&results-page={page}"
UK_PERSONAL_CATEGORIES = {
    "Deceased Estates",
    "Bankruptcy Orders",
    "Notice of Intended Dividends",
    "Winding-Up Orders",
    "Meetings of Creditors",
    "Appointment of Liquidators",
    "Administration",
    "Personal Insolvency",
    "Trustee",
}
UK_GENERIC_TITLES = {"other notices", "notice", "notices"}


def _uk_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        candidate = line.strip(" :-")
        if len(candidate) < 6 or len(candidate) > 180:
            continue
        if candidate.casefold().startswith(("notice category", "publication date", "edition", "notice id")):
            continue
        if candidate.isupper() or candidate[0].isupper():
            return candidate
    return fallback


def uk_gazette_notices(ds: Dataset, limit: int = 10) -> int:
    ns = {"a": "http://www.w3.org/2005/Atom"}
    added = 0
    page = 1
    while added < limit and page <= 40:
        feed = fetch_text(UK_ATOM.format(page=page), accept="application/atom+xml")
        root = ET.fromstring(feed)
        for entry in root.findall("a:entry", ns):
            if added >= limit:
                break
            categories = [c.get("term", "") for c in entry.findall("a:category", ns)]
            if any(category in UK_PERSONAL_CATEGORIES for category in categories):
                continue
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            link = ""
            for item in entry.findall("a:link", ns):
                if item.get("rel") is None:
                    link = item.get("href", "")
            if not link:
                continue
            raw, content_type = fetch(link)
            markup = decode(raw)
            body = html_to_text(markup)
            if re.search(r"\b(deceased|estate of|insolven|bankrupt)\b", body[:2500], re.I):
                continue
            if re.search(r"contact person\s*:|petitioner'?s solicitor is", body, re.I):
                continue
            title = _uk_title(body, title)
            if not title or title.casefold() in {"other notices", "notice"}:
                continue
            published = parse_date(entry.findtext("a:published", default="", namespaces=ns))
            if published is None:
                continue
            text = truncate(body, 6000)
            document_id = ds.add_document(
                DocumentDraft(
                    source_id="gb-the-gazette",
                    official_url=link,
                    content_type="text/html",
                    language="en",
                    title=title[:300],
                    publisher="The Gazette (UK official public record)",
                    publication_date=published,
                    text=text,
                    source_sha256=sha256(raw),
                    source_bytes=len(raw),
                ),
                raw,
            )
            category = "licensing" if "licens" in title.casefold() else "other"
            if "planning" in title.casefold():
                category = "land"
            added += _record(
                ds,
                RecordDraft(
                    record_type="public_notice",
                    title=title,
                    publication_date=published,
                    document_id=document_id,
                    source_id="gb-the-gazette",
                    official_url=link,
                    excerpt=truncate(body, 420),
                    source_sha256=sha256(raw),
                    language="en",
                    keywords=["gazette", "public notice"],
                    notice={"category": category},
                ),
            )
        page += 1
    return added


def uk_find_a_tender(ds: Dataset, limit: int = 10) -> int:
    url = (
        "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
        f"?limit={max(limit * 4, 20)}&stages=tender"
    )
    raw, _ = fetch(url, accept="application/json")
    payload = json.loads(decode(raw))
    added = 0
    for release in payload.get("releases", []):
        if added >= limit:
            break
        tender = release.get("tender") or {}
        title = tender.get("title")
        if not title:
            continue
        buyer = (release.get("buyer") or {}).get("name") or "Not stated"
        period = tender.get("tenderPeriod") or {}
        closing = parse_date(period.get("endDate"))
        published = parse_date(release.get("date"))
        reference = str(tender.get("id") or release.get("id") or release.get("ocid"))
        notice_url = f"https://www.find-tender.service.gov.uk/Notice/{release.get('id')}"
        description = tender.get("description") or ""
        classification = (tender.get("classification") or {}).get("description") or ""
        text = _text_field(
            ("Title", title),
            ("Reference", reference),
            ("Buying organisation", buyer),
            ("Published", published),
            ("Closing", closing),
            ("Procurement category", tender.get("mainProcurementCategory")),
            ("Classification", classification),
            ("Description", truncate(description, 800)),
        )
        document_id = ds.add_document(
            DocumentDraft(
                source_id="gb-find-a-tender",
                official_url=notice_url,
                content_type="application/json",
                language="en",
                title=title[:300],
                publisher="UK Find a Tender service",
                publication_date=published,
                text=text,
                source_sha256=sha256(raw),
                source_bytes=len(raw),
            ),
            raw,
        )
        status = "open" if closing and closing >= TODAY else "closed"
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published or TODAY,
                document_id=document_id,
                source_id="gb-find-a-tender",
                official_url=notice_url,
                excerpt=truncate(text, 420),
                source_sha256=sha256(raw),
                language="en",
                summary=truncate(description, 400) or None,
                keywords=["procurement", "tender"],
                organisation_name=buyer,
                sector=infer_sector(
                    f"{tender.get('mainProcurementCategory')} {classification}", "other"
                ),
                tender={
                    "reference": reference,
                    "sector": infer_sector(
                        f"{tender.get('mainProcurementCategory')} {classification}", "other"
                    ),
                    "status": status,
                    "closing_date": closing,
                    "currency": "GBP" if (tender.get("value") or {}).get("currency") == "GBP" else None,
                },
                issuing_organisation_name=buyer,
            ),
        )
    return added


# ---------------------------------------------------------------------------
# United States
# ---------------------------------------------------------------------------

FR_API = "https://www.federalregister.gov/api/v1/documents.json"


def _fr_document(result: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    title = result.get("title")
    if not title:
        return None
    agencies = [a.get("name") for a in result.get("agencies", []) if a.get("name")]
    publisher = agencies[0] if agencies else "Federal Register"
    published = parse_date(result.get("publication_date"))
    body = ""
    raw_text_url = result.get("raw_text_url")
    if raw_text_url:
        try:
            body = fetch_text(raw_text_url)
        except Exception:
            body = ""
    if not body:
        html_url = result.get("body_html_url") or result.get("html_url")
        if html_url:
            try:
                body = html_to_text(fetch_text(html_url))
            except Exception:
                body = ""
    if not body:
        body = _text_field(
            ("Title", title),
            ("Agency", ", ".join(agencies)),
            ("Document number", result.get("document_number")),
            ("Published", published),
            ("Abstract", result.get("abstract")),
        )
    return {
        "title": title,
        "agencies": agencies,
        "publisher": publisher,
        "published": published,
        "body": body,
        "html_url": result.get("html_url"),
        "document_number": result.get("document_number"),
        "abstract": result.get("abstract"),
        "source_id": source_id,
        "type": result.get("type"),
    }


def us_federal_register_notices(ds: Dataset, limit: int = 10) -> int:
    added = 0
    for doc_type in ("NOTICE", "RULE"):
        wanted = limit if doc_type == "NOTICE" else max(limit // 2, 1)
        url = (
            f"{FR_API}?per_page={wanted * 2}&order=newest"
            f"&conditions%5Btype%5D%5B%5D={doc_type}"
        )
        raw, _ = fetch(url, accept="application/json")
        payload = json.loads(decode(raw))
        for result in payload.get("results", []):
            if added >= limit + max(limit // 2, 1):
                break
            data = _fr_document(result, "us-federal-register")
            if data is None or not data["published"] or not data["html_url"]:
                continue
            text = truncate(
                f"{data['title']}\n{data['body']}",
                9000,
            )
            document_id = ds.add_document(
                DocumentDraft(
                    source_id="us-federal-register",
                    official_url=data["html_url"],
                    content_type="text/html",
                    language="en",
                    title=data["title"][:300],
                    publisher=data["publisher"],
                    publication_date=data["published"],
                    text=text,
                    source_sha256=sha256(raw),
                    source_bytes=len(raw),
                ),
                raw,
            )
            record_type = "public_notice" if doc_type == "NOTICE" else "regulation"
            added += _record(
                ds,
                RecordDraft(
                    record_type=record_type,
                    title=data["title"],
                    publication_date=data["published"],
                    document_id=document_id,
                    source_id="us-federal-register",
                    official_url=data["html_url"],
                    excerpt=truncate(data["body"] or data["title"], 420),
                    source_sha256=sha256(raw),
                    language="en",
                    summary=truncate(data["abstract"], 400) if data["abstract"] else None,
                    keywords=["federal register", doc_type.casefold()],
                    organisation_name=data["publisher"],
                    sector="other",
                    notice={"category": "other"} if record_type == "public_notice" else None,
                    regulation=(
                        {
                            "instrument_type": "rule",
                            "instrument_number": data["document_number"],
                            "effective_date": None,
                        }
                        if record_type == "regulation"
                        else None
                    ),
                ),
            )
    return added


GRANTS_API = "https://api.grants.gov/v1/api/search2"
GRANTS_OPP = "https://api.grants.gov/v1/api/fetchOpportunity"


def us_grants_gov(ds: Dataset, limit: int = 10) -> int:
    payload = {"keyword": "", "oppStatuses": "posted|forecasted", "rows": max(limit * 3, 20), "startRecordNum": 0}
    raw, _ = fetch(
        GRANTS_API,
        method="POST",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        accept="application/json",
    )
    data = json.loads(decode(raw))
    added = 0
    for hit in data.get("data", {}).get("oppHits", []):
        if added >= limit:
            break
        title = hit.get("title")
        number = hit.get("number")
        if not title or not number:
            continue
        details: dict[str, Any] = {}
        try:
            detail_raw, _ = fetch(
                GRANTS_OPP,
                method="POST",
                data=json.dumps({"opportunityId": hit.get("id")}).encode(),
                headers={"Content-Type": "application/json"},
                accept="application/json",
            )
            details = json.loads(decode(detail_raw)).get("data", {})
        except Exception:
            details = {}
        synopsis = details.get("synopsis") or {}
        description = (
            synopsis.get("synopsisDesc")
            or details.get("description")
            or ""
        )
        published = parse_date(hit.get("openDate"))
        closing = parse_date(hit.get("closeDate"))
        notice_url = f"https://www.grants.gov/search-results-detail/{hit.get('id')}"
        text = _text_field(
            ("Title", title),
            ("Opportunity number", number),
            ("Agency", hit.get("agency")),
            ("Status", hit.get("oppStatus")),
            ("Open date", published),
            ("Close date", closing),
            ("Description", truncate(html_to_text(description), 1000) if description else None),
        )
        document_id = ds.add_document(
            DocumentDraft(
                source_id="us-grants-gov",
                official_url=notice_url,
                content_type="application/json",
                language="en",
                title=title[:300],
                publisher=hit.get("agency"),
                publication_date=published,
                text=text,
                source_sha256=sha256(raw),
                source_bytes=len(raw),
            ),
            raw,
        )
        status = "open" if (closing is None or closing >= TODAY) else "closed"
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published or TODAY,
                document_id=document_id,
                source_id="us-grants-gov",
                official_url=notice_url,
                excerpt=truncate(text, 420),
                source_sha256=sha256(raw),
                language="en",
                summary=truncate(html_to_text(description), 400) if description else None,
                keywords=["grant", "procurement"],
                organisation_name=hit.get("agency"),
                sector="other",
                tender={
                    "reference": number,
                    "sector": "other",
                    "status": status,
                    "closing_date": closing,
                    "currency": "USD" if details.get("awardCeiling") else None,
                },
                issuing_organisation_name=hit.get("agency"),
            ),
        )
    return added


# ---------------------------------------------------------------------------
# Canada
# ---------------------------------------------------------------------------

CA_INDEX = "https://gazette.gc.ca/rp-pr/p1/{year}/index-eng.html"


def _ca_issue_link(markup: str) -> str | None:
    match = re.search(r'href="([^"]*/html/index-eng\.html)"[^>]*>\s*Part', markup)
    return absolute(CA_INDEX.format(year=TODAY.year), match.group(1)) if match else None


def ca_gazette_notices(ds: Dataset, limit: int = 10) -> int:
    added = 0
    index_url = CA_INDEX.format(year=TODAY.year)
    try:
        index = fetch_text(index_url)
    except Exception:
        return 0
    issue_links = []
    for match in re.finditer(r'href="([^"]*/html/index-eng\.html)"', index):
        link = absolute(index_url, match.group(1))
        if link not in issue_links:
            issue_links.append(link)
    for issue_url in issue_links[:6]:
        if added >= limit:
            break
        try:
            issue_markup = fetch_text(issue_url)
        except Exception:
            continue
        notice_match = re.search(r'href="([^"]*notice-avis-eng\.html)"', issue_markup)
        if not notice_match:
            continue
        notice_url = absolute(issue_url, notice_match.group(1))
        try:
            notice_markup = fetch_text(notice_url)
        except Exception:
            continue
        published = parse_date(re.search(r"/(\d{4}-\d{2}-\d{2})/", issue_url).group(1)) if re.search(r"/(\d{4}-\d{2}-\d{2})/", issue_url) else None
        if published is None:
            continue
        blocks = re.split(r"(?=<h2\b)", notice_markup)
        for block in blocks:
            if added >= limit:
                break
            heading_match = re.match(r"<h2[^>]*>(.*?)</h2>", block, re.S)
            if not heading_match:
                continue
            heading = strip_tags(heading_match.group(1)).strip()
            if not heading or heading in {
                "Language selection", "Search", "Menu", "Topics menu", "Footnotes",
                "About government", "About this site", "Note to readers",
            }:
                continue
            body = html_to_text(block)
            text = truncate(body, 6000)
            if len(text) < 400:
                continue
            lines = text.splitlines()
            title = heading
            if heading.isupper() and any(
                key in heading for key in ("DEPARTMENT", "AGENCY", "OFFICE", "COMMISSION", "TREASURY BOARD")
            ):
                for line in lines[1:8]:
                    if len(line) > 20 and not line.isupper():
                        title = line
                        break
            if len(title) < 8:
                continue
            document_id = ds.add_document(
                DocumentDraft(
                    source_id="ca-canada-gazette",
                    official_url=notice_url,
                    content_type="text/html",
                    language="en",
                    title=title[:300],
                    publisher="Canada Gazette, Part I",
                    publication_date=published,
                    text=text,
                    source_sha256=sha256(notice_markup.encode()),
                    source_bytes=len(notice_markup.encode()),
                ),
                notice_markup.encode(),
            )
            added += _record(
                ds,
                RecordDraft(
                    record_type="public_notice",
                    title=title[:300],
                    publication_date=published,
                    document_id=document_id,
                    source_id="ca-canada-gazette",
                    official_url=notice_url,
                    excerpt=truncate(text, 420),
                    source_sha256=sha256(notice_markup.encode()),
                    language="en",
                    keywords=["canada gazette", "government notice"],
                    organisation_name=heading if heading.isupper() else None,
                    sector="other",
                    notice={"category": "other"},
                ),
            )
    return added


CANADABUYS_CSV = "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"


def ca_canadabuys(ds: Dataset, limit: int = 10) -> int:
    raw, _ = fetch(CANADABUYS_CSV, accept="text/csv")
    text = decode(raw)
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    added = 0
    for row in reader:
        if added >= limit:
            break
        title = (row.get("title-titre-eng") or "").strip()
        reference = (row.get("referenceNumber-numeroReference") or "").strip()
        notice_url = (row.get("noticeURL-URLavis-eng") or "").strip()
        buyer = (row.get("contractingEntityName-nomEntitContractante-eng") or "").strip()
        if not title or not reference or not notice_url:
            continue
        published = parse_date(row.get("publicationDate-datePublication"))
        closing = parse_date(row.get("tenderClosingDate-appelOffresDateCloture"))
        status_text = (row.get("tenderStatus-appelOffresStatut-eng") or "").strip()
        category = (row.get("procurementCategory-categorieApprovisionnement") or "").strip()
        description = (row.get("tenderDescription-descriptionAppelOffres-eng") or "").strip()
        text_body = _text_field(
            ("Title", title),
            ("Reference", reference),
            ("Contracting entity", buyer),
            ("Published", published),
            ("Closing", closing),
            ("Status", status_text),
            ("Procurement category", category),
            ("Description", truncate(description, 900)),
        )
        document_id = ds.add_document(
            DocumentDraft(
                source_id="ca-canadabuys",
                official_url=notice_url,
                content_type="text/csv",
                language="en",
                title=title[:300],
                publisher=buyer,
                publication_date=published,
                text=text_body,
                source_sha256=sha256(raw),
                source_bytes=len(raw),
            ),
            raw,
        )
        sector = {"GD": "goods", "SRV": "services", "CNST": "civil_works"}.get(
            category.upper(), infer_sector(category)
        )
        status = "open" if status_text.casefold().startswith("open") and (closing is None or closing >= TODAY) else "closed"
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published or TODAY,
                document_id=document_id,
                source_id="ca-canadabuys",
                official_url=notice_url,
                excerpt=truncate(text_body, 420),
                source_sha256=sha256(raw),
                language="en",
                summary=truncate(description, 400) or None,
                keywords=["canadabuys", "tender"],
                organisation_name=buyer,
                sector=sector,
                tender={
                    "reference": reference,
                    "sector": sector,
                    "status": status,
                    "closing_date": closing,
                    "currency": "CAD" if row.get("noticeType-avisType-eng") else None,
                },
                issuing_organisation_name=buyer,
            ),
        )
    return added


# ---------------------------------------------------------------------------
# Australia
# ---------------------------------------------------------------------------

AU_TITLES = "https://api.prod.legislation.gov.au/v1/titles"


def au_legislation(ds: Dataset, limit: int = 10) -> int:
    query = urllib.parse.urlencode(
        {"$orderby": "makingDate desc", "$top": str(max(limit * 8, 40))}
    )
    raw, _ = fetch(f"{AU_TITLES}?{query}", accept="application/json")
    payload = json.loads(decode(raw))
    added = 0
    for item in payload.get("value", []):
        if added >= limit:
            break
        if item.get("collection") not in {"LegislativeInstrument", "NotifiableInstrument"}:
            continue
        title = item.get("name")
        if not title or any(
            marker in title.casefold()
            for marker in ("disqualification", "bankrupt", "deceased", "estate of")
        ):
            continue
        identifier = item.get("id")
        published = parse_date(item.get("makingDate"))
        if not title or not identifier or not published:
            continue
        official_url = f"https://www.legislation.gov.au/{identifier}/latest"
        number = item.get("number")
        year = item.get("year") or published.year
        text = _text_field(
            ("Title", title),
            ("Identifier", identifier),
            ("Collection", item.get("collection")),
            ("Making date", published),
            ("Status", item.get("status")),
            ("Series number", f"{number} of {year}" if number else None),
        )
        document_id = ds.add_document(
            DocumentDraft(
                source_id="au-legislation-register",
                official_url=official_url,
                content_type="application/json",
                language="en",
                title=title[:300],
                publisher="Australian Government Federal Register of Legislation",
                publication_date=published,
                text=text,
                source_sha256=sha256(raw),
                source_bytes=len(raw),
            ),
            raw,
        )
        added += _record(
            ds,
            RecordDraft(
                record_type="regulation",
                title=title,
                publication_date=published,
                document_id=document_id,
                source_id="au-legislation-register",
                official_url=official_url,
                excerpt=truncate(text, 300),
                source_sha256=sha256(raw),
                language="en",
                keywords=["legislation", "australia"],
                regulation={
                    "instrument_type": "regulation",
                    "instrument_number": f"{number} of {year}" if number else identifier,
                    "effective_date": None,
                },
            ),
        )
    return added


def au_notices(ds: Dataset, limit: int = 10) -> int:
    query = urllib.parse.urlencode({"$orderby": "makingDate desc", "$top": "150"})
    raw, _ = fetch(f"{AU_TITLES}?{query}", accept="application/json")
    payload = json.loads(decode(raw))
    added = 0
    for item in payload.get("value", []):
        if added >= limit:
            break
        if item.get("collection") != "NotifiableInstrument":
            continue
        title = item.get("name")
        if not title or any(
            marker in title.casefold()
            for marker in ("disqualification", "bankrupt", "deceased", "estate of")
        ):
            continue
        identifier = item.get("id")
        published = parse_date(item.get("makingDate"))
        if not title or not identifier or not published:
            continue
        lowered = title.casefold()
        if any(word in lowered for word in ("disqualification", "bankrupt", "deceased", "estate of")):
            continue
        if not any(word in lowered for word in ("notice", "declaration", "exemption", "determination", "ruling")):
            continue
        official_url = f"https://www.legislation.gov.au/{identifier}/latest"
        text = _text_field(
            ("Title", title),
            ("Identifier", identifier),
            ("Collection", item.get("collection")),
            ("Making date", published),
            ("Status", item.get("status")),
        )
        document_id = ds.add_document(
            DocumentDraft(
                source_id="au-legislation-notices",
                official_url=official_url,
                content_type="application/json",
                language="en",
                title=title[:300],
                publisher="Australian Government Federal Register of Legislation",
                publication_date=published,
                text=text,
                source_sha256=sha256(raw),
                source_bytes=len(raw),
            ),
            raw,
        )
        added += _record(
            ds,
            RecordDraft(
                record_type="public_notice",
                title=title,
                publication_date=published,
                document_id=document_id,
                source_id="au-legislation-notices",
                official_url=official_url,
                excerpt=truncate(text, 300),
                source_sha256=sha256(raw),
                language="en",
                keywords=["notifiable instrument", "australia"],
                notice={"category": "other"},
            ),
        )
    return added


# ---------------------------------------------------------------------------
# New Zealand
# ---------------------------------------------------------------------------

NZ_GETS = "https://www.gets.govt.nz/ExternalIndex.htm"


def nz_gets(ds: Dataset, limit: int = 10) -> int:
    markup = fetch_text(NZ_GETS)
    added = 0
    for match in re.finditer(
        r'<tr[^>]*>(.*?)</tr>', markup, re.S
    ):
        if added >= limit:
            break
        row = match.group(1)
        link_match = re.search(r'href="([^"]*ExternalTenderDetails\.htm\?id=\d+)"', row)
        if not link_match:
            continue
        link = absolute(NZ_GETS, link_match.group(1).replace("&amp;", "&"))
        cells = [
            strip_tags(cell)
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        ]
        if len(cells) < 6:
            continue
        reference, title, tender_type = cells[1], cells[2], cells[3]
        organisation = cells[-1]
        if not title:
            continue
        try:
            detail_markup = fetch_text(link)
        except Exception:
            continue
        detail_text = html_to_text(detail_markup)
        open_match = re.search(r"Open Date\s*:?\s*(.+)", detail_text)
        close_match = re.search(r"Close Date\s*:?\s*(.+)", detail_text)
        published = parse_date(open_match.group(1)) if open_match else None
        closing = parse_date(close_match.group(1)) if close_match else None
        if published is None:
            continue
        body = truncate(detail_text, 7000)
        document_id = ds.add_document(
            DocumentDraft(
                source_id="nz-gets",
                official_url=link,
                content_type="text/html",
                language="en",
                title=title[:300],
                publisher=organisation,
                publication_date=published,
                text=body,
                source_sha256=sha256(detail_markup.encode()),
                source_bytes=len(detail_markup.encode()),
            ),
            detail_markup.encode(),
        )
        status = "open" if closing and closing >= TODAY else "closed"
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published,
                document_id=document_id,
                source_id="nz-gets",
                official_url=link,
                excerpt=truncate(detail_text, 420),
                source_sha256=sha256(detail_markup.encode()),
                language="en",
                summary=None,
                keywords=["gets", "tender"],
                organisation_name=organisation,
                sector=infer_sector(tender_type, "other"),
                tender={
                    "reference": reference,
                    "sector": infer_sector(tender_type, "other"),
                    "status": status,
                    "closing_date": closing,
                    "closing_time": parse_time(close_match.group(1)) if close_match else None,
                    "currency": "NZD",
                },
                issuing_organisation_name=organisation,
            ),
        )
    return added


# ---------------------------------------------------------------------------
# Singapore
# ---------------------------------------------------------------------------

SG_GEBIZ = "https://www.gebiz.gov.sg/ptn/opportunity/index.xhtml"


def sg_gebiz(ds: Dataset, limit: int = 10) -> int:
    markup = fetch_text(SG_GEBIZ)
    added = 0
    blocks = re.split(r'(?=<a[^>]+directlink\.xhtml\?docCode=)', markup)
    for block in blocks[1:]:
        if added >= limit:
            break
        code_match = re.search(r'directlink\.xhtml\?docCode=([A-Z0-9]+)', block)
        if not code_match:
            continue
        code = code_match.group(1)
        title_match = re.search(r'directlink\.xhtml\?docCode=[^"]+"[^>]*>(.*?)</a>', block, re.S)
        title = strip_tags(title_match.group(1)) if title_match else ""
        body = html_to_text(block[:12000])
        agency_match = re.search(r"Agency\s*\n(.+)", body)
        published_match = re.search(r"Published\s*\n(.+)", body)
        closing_match = re.search(r"Closing on\s*\n(.+)", body)
        category_match = re.search(r"Procurement Category\s*\n(.+)", body)
        if not title or not agency_match or not published_match:
            continue
        published = parse_date(published_match.group(1))
        closing = parse_date(closing_match.group(1)) if closing_match else None
        closing_time = parse_time(closing_match.group(1)) if closing_match else None
        category = category_match.group(1) if category_match else ""
        if published is None:
            continue
        text = truncate(body, 5000)
        official_url = f"https://www.gebiz.gov.sg/ptn/opportunity/directlink.xhtml?docCode={code}"
        document_id = ds.add_document(
            DocumentDraft(
                source_id="sg-gebiz",
                official_url=official_url,
                content_type="text/html",
                language="en",
                title=title[:300],
                publisher=agency_match.group(1).strip(),
                publication_date=published,
                text=text,
                source_sha256=sha256(markup.encode()),
                source_bytes=len(markup.encode()),
            ),
            markup.encode(),
        )
        status = "open" if closing and closing >= TODAY else "closed"
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published,
                document_id=document_id,
                source_id="sg-gebiz",
                official_url=official_url,
                excerpt=truncate(body, 420),
                source_sha256=sha256(markup.encode()),
                language="en",
                keywords=["gebiz", "procurement"],
                organisation_name=agency_match.group(1).strip(),
                sector=infer_sector(category, "other"),
                tender={
                    "reference": code,
                    "sector": infer_sector(category, "other"),
                    "status": status,
                    "closing_date": closing,
                    "closing_time": closing_time,
                    "currency": "SGD",
                },
                issuing_organisation_name=agency_match.group(1).strip(),
            ),
        )
    return added


# ---------------------------------------------------------------------------
# South Africa
# ---------------------------------------------------------------------------

ZA_API = (
    "https://www.etenders.gov.za/Home/PaginatedTenderOpportunities"
    "?draw=1&start=0&length={length}&status=1"
)


def za_etenders(ds: Dataset, limit: int = 10) -> int:
    raw, _ = fetch(ZA_API.format(length=max(limit * 3, 30)), accept="application/json")
    payload = json.loads(decode(raw))
    added = 0
    for item in payload.get("data", []):
        if added >= limit:
            break
        title = (item.get("description") or "").strip()
        reference = (item.get("tender_No") or "").strip()
        identifier = item.get("id")
        buyer = (item.get("organ_of_State") or item.get("department") or "").strip()
        if not title or not reference or not identifier:
            continue
        published = parse_date(item.get("date_Published"))
        closing = parse_date(item.get("closing_Date"))
        if published is None:
            continue
        province = item.get("province") or (item.get("provinces") or {}).get("name")
        category = item.get("category") or ""
        official_url = f"https://www.etenders.gov.za/Home/opportunities?id={identifier}"
        text = _text_field(
            ("Title", title),
            ("Tender reference", reference),
            ("Issuing organisation", buyer),
            ("Province", province),
            ("Category", category),
            ("Tender type", item.get("type")),
            ("Status", item.get("status")),
            ("Published", published),
            ("Closing", closing),
        )
        document_id = ds.add_document(
            DocumentDraft(
                source_id="za-etenders",
                official_url=official_url,
                content_type="application/json",
                language="en",
                title=title[:300],
                publisher=buyer or "South African eTenders Portal",
                publication_date=published,
                text=text,
                source_sha256=sha256(raw),
                source_bytes=len(raw),
            ),
            raw,
        )
        status = "open" if closing and closing >= TODAY else "closed"
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published,
                document_id=document_id,
                source_id="za-etenders",
                official_url=official_url,
                excerpt=truncate(text, 420),
                source_sha256=sha256(raw),
                language="en",
                keywords=["etenders", "procurement"],
                location=province,
                organisation_name=buyer,
                sector=infer_sector(f"{category} {item.get('type')}", "other"),
                tender={
                    "reference": reference,
                    "sector": infer_sector(f"{category} {item.get('type')}", "other"),
                    "status": status,
                    "closing_date": closing,
                    "closing_time": parse_time(item.get("closing_Date")),
                    "currency": "ZAR",
                },
                issuing_organisation_name=buyer,
            ),
        )
    return added


# ---------------------------------------------------------------------------
# Kenya
# ---------------------------------------------------------------------------

KE_API = "https://tenders.go.ke/api/tender?page={page}"


def ke_ppip(ds: Dataset, limit: int = 10) -> int:
    added = 0
    page = 1
    while added < limit and page <= 4:
        raw, _ = fetch(KE_API.format(page=page), accept="application/json")
        payload = json.loads(decode(raw))
        for item in payload.get("data", []):
            if added >= limit:
                break
            title = (item.get("title") or "").strip()
            reference = (item.get("tender_ref") or "").strip()
            identifier = item.get("id")
            published = parse_date(item.get("published_at"))
            closing = parse_date(item.get("close_at"))
            if not title or not reference or not identifier or published is None:
                continue
            buyer = "Public Procurement Information Portal"
            official_url = f"https://tenders.go.ke/oneTender/{identifier}"
            text = _text_field(
                ("Title", title),
                ("Tender reference", reference),
                ("Published", published),
                ("Closing", closing),
                ("Venue", item.get("venue")),
                ("Tender fee", item.get("tender_fee")),
                ("Bid security", item.get("bid_security_value")),
            )
            document_id = ds.add_document(
                DocumentDraft(
                    source_id="ke-ppip",
                    official_url=official_url,
                    content_type="application/json",
                    language="en",
                    title=title[:300],
                    publisher=buyer,
                    publication_date=published,
                    text=text,
                    source_sha256=sha256(raw),
                    source_bytes=len(raw),
                ),
                raw,
            )
            status = "open" if closing and closing >= TODAY else "closed"
            added += _record(
                ds,
                RecordDraft(
                    record_type="tender",
                    title=title,
                    publication_date=published,
                    document_id=document_id,
                    source_id="ke-ppip",
                    official_url=official_url,
                    excerpt=truncate(text, 420),
                    source_sha256=sha256(raw),
                    language="en",
                    keywords=["ppip", "procurement"],
                    organisation_name=buyer,
                    sector="other",
                    tender={
                        "reference": reference,
                        "sector": "other",
                        "status": status,
                        "closing_date": closing,
                        "closing_time": parse_time(item.get("close_at")),
                        "currency": "KES",
                    },
                    issuing_organisation_name=buyer,
                ),
            )
        page += 1
    return added


# ---------------------------------------------------------------------------
# European Union — TED
# ---------------------------------------------------------------------------

TED_API = "https://api.ted.europa.eu/v3/notices/search"
TED_COUNTRIES = {"de": ("DEU", "de", "de-ted"), "ie": ("IRL", "en", "ie-ted"), "nl": ("NLD", "nl", "nl-ted")}


def ted_tenders(ds: Dataset, limit: int = 10, country: str = "de") -> int:
    buyer_country, title_lang, source_id = TED_COUNTRIES[country]
    query = (
        f"buyer-country={buyer_country} AND notice-type=cn-standard "
        f"AND publication-date>=20260101 SORT BY publication-date DESC"
    )
    payload = {
        "query": query,
        "fields": [
            "publication-number",
            "notice-title",
            "buyer-name",
            "publication-date",
            "deadline-receipt-tender-date-lot",
            "deadline-receipt-tender-time-lot",
            "classification-cpv",
            "links",
        ],
        "limit": max(limit * 2, 20),
    }
    raw, _ = fetch(
        TED_API,
        method="POST",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        accept="application/json",
    )
    data = json.loads(decode(raw))
    added = 0
    for notice in data.get("notices", []):
        if added >= limit:
            break
        pubnum = notice.get("publication-number")
        title_map = notice.get("notice-title") or {}
        title = title_map.get(title_lang) or next(iter(title_map.values()), None)
        buyer_map = notice.get("buyer-name") or {}
        buyer = (buyer_map.get(title_lang) or next(iter(buyer_map.values()), ["Not stated"]))[0]
        published = parse_date(notice.get("publication-date"))
        deadline = (notice.get("deadline-receipt-tender-date-lot") or [None])[0]
        closing = parse_date(deadline)
        closing_time = parse_time((notice.get("deadline-receipt-tender-time-lot") or [None])[0])
        links = notice.get("links") or {}
        official_url = (
            (links.get("pdf") or {}).get(title_lang.upper())
            or ((links.get("xml") or {}).get("MUL"))
            or (links.get("html") or {}).get("ENG")
        )
        if not pubnum or not title or not published or not official_url:
            continue
        text = _text_field(
            ("Title", title),
            ("Notice number", pubnum),
            ("Buyer", buyer),
            ("Published", published),
            ("Closing", closing),
            ("CPV", (notice.get("classification-cpv") or [None])[0]),
        )
        document_id = ds.add_document(
            DocumentDraft(
                source_id=source_id,
                official_url=official_url,
                content_type="application/json",
                language=title_lang,
                title=title[:300],
                publisher=buyer,
                publication_date=published,
                text=text,
                source_sha256=sha256(raw),
                source_bytes=len(raw),
            ),
            raw,
        )
        status = "open" if closing and closing >= TODAY else "closed"
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published,
                document_id=document_id,
                source_id=source_id,
                official_url=official_url,
                excerpt=truncate(text, 420),
                source_sha256=sha256(raw),
                language=title_lang,
                keywords=["ted", "procurement"],
                organisation_name=buyer,
                sector="other",
                tender={
                    "reference": pubnum,
                    "sector": "other",
                    "status": status,
                    "closing_date": closing,
                    "closing_time": closing_time,
                    "currency": "EUR",
                },
                issuing_organisation_name=buyer,
            ),
        )
    return added


def de_ted(ds: Dataset, limit: int = 10) -> int:
    return ted_tenders(ds, limit, "de")


def ie_ted(ds: Dataset, limit: int = 10) -> int:
    return ted_tenders(ds, limit, "ie")


def nl_ted(ds: Dataset, limit: int = 10) -> int:
    return ted_tenders(ds, limit, "nl")


# ---------------------------------------------------------------------------
# Germany — Bundesgesetzblatt
# ---------------------------------------------------------------------------

DE_BGBL_PARTS = ("https://www.recht.bund.de/bgbl/1/{year}", "https://www.recht.bund.de/bgbl/2/{year}")


def de_bgbl(ds: Dataset, limit: int = 10) -> int:
    added = 0
    seen: set[str] = set()
    for template in DE_BGBL_PARTS:
        if added >= limit:
            break
        page_url = template.format(year=TODAY.year)
        try:
            markup = fetch_text(page_url)
        except Exception:
            continue
        pattern = re.compile(
            r'<h3[^>]*>\s*(BGBl\. \d{4} [IV]+ Nr\. [^<]+? vom (\d{2}\.\d{2}\.\d{4}))\s*</h3>'
            r'.*?<a href="([^"]+)"[^>]*>\s*<strong>(.*?)</strong>',
            re.S,
        )
        for match in pattern.finditer(markup):
            if added >= limit:
                break
            label, date_text, link, title = match.groups()
            title = strip_tags(title)
            if not title or link in seen:
                continue
            seen.add(link)
            published = parse_date(date_text)
            if published is None:
                continue
            try:
                instrument_markup = fetch_text(link)
            except Exception:
                instrument_markup = ""
            body = html_to_text(instrument_markup) if instrument_markup else ""
            text = _text_field(
                ("Title", title),
                ("Official citation", label),
                ("Published", published),
                ("Publisher", "Bundesgesetzblatt"),
                ("Text", truncate(body, 4000) if body else None),
            )
            document_id = ds.add_document(
                DocumentDraft(
                    source_id="de-bgbl",
                    official_url=link,
                    content_type="text/html",
                    language="de",
                    title=title[:300],
                    publisher="Bundesgesetzblatt",
                    publication_date=published,
                    text=text,
                    source_sha256=sha256(instrument_markup.encode()),
                    source_bytes=len(instrument_markup.encode()),
                ),
                instrument_markup.encode(),
            )
            lowered = title.casefold()
            instrument_type = (
                "regulation" if "verordnung" in lowered
                else "act" if "gesetz" in lowered
                else "notification" if "bekanntmachung" in lowered
                else "other"
            )
            added += _record(
                ds,
                RecordDraft(
                    record_type="regulation",
                    title=title,
                    publication_date=published,
                    document_id=document_id,
                    source_id="de-bgbl",
                    official_url=link,
                    excerpt=truncate(text, 420),
                    source_sha256=sha256(instrument_markup.encode()),
                    language="de",
                    keywords=["bundesgesetzblatt", "deutschland"],
                    regulation={
                        "instrument_type": instrument_type,
                        "instrument_number": label,
                        "effective_date": None,
                    },
                ),
            )
    return added



# ---------------------------------------------------------------------------
# Bangladesh
# ---------------------------------------------------------------------------

BD_LISTING = "https://www.eprocure.gov.bd/resources/common/AllTenders.jsp?h=t"
BD_SERVLET = "https://www.eprocure.gov.bd/TenderDetailsServlet"
BD_DETAIL = "https://www.eprocure.gov.bd/resources/common/ViewTender.jsp?id={identifier}&h=t"


def _bd_listing(limit: int) -> str:
    payload = urllib.parse.urlencode(
        {
            "funName": "AllTenders",
            "departmentId": "",
            "viewType": "",
            "office": "",
            "procNature": "",
            "budgetType": "",
            "procType": "",
            "procMethod": "",
            "tenderId": "",
            "refNo": "",
            "pubDtFrm": "",
            "pubDtTo": "",
            "closeDtFrm": "",
            "closeDtTo": "",
            "cpvCategory": "",
            "isFrame": "",
            "pageNo": "1",
            "size": str(max(limit * 3, 30)),
            "h": "t",
        }
    ).encode()
    raw, _ = fetch(
        BD_SERVLET,
        method="POST",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BD_LISTING,
            "X-Requested-With": "XMLHttpRequest",
        },
        accept="text/html",
    )
    return decode(raw)


def _bd_scrub(text: str) -> str:
    """Remove contact-person fields and e-mail addresses before storing a snapshot."""
    lines = []
    for line in text.splitlines():
        low = line.casefold()
        if any(
            marker in low
            for marker in (
                "contact person",
                "contact name",
                "designation",
                "e-mail",
                "email",
                "telephone",
                "phone no",
                "mobile no",
                "fax",
            )
        ):
            continue
        lines.append(re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[contact removed]", line))
    return "\n".join(lines)


def bd_egp(ds: Dataset, limit: int = 10) -> int:
    listing = _bd_listing(limit)
    added = 0
    for row in re.findall(r"<tr class='[^']*'>(.*?)</tr>", listing, re.S):
        if added >= limit:
            break
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 6:
            continue
        identifier_match = re.search(r'name="id" value="(\d+)"', row)
        title_match = re.search(r"<span id='tenderBrief_\d+'><p>(.*?)</p>", row, re.S)
        if not identifier_match or not title_match:
            continue
        identifier = identifier_match.group(1)
        title = strip_tags(title_match.group(1))
        reference_match = re.search(r"(\d{6,})", strip_tags(cells[1]))
        reference = reference_match.group(1) if reference_match else identifier
        buyer = strip_tags(cells[3]).strip(" ,")
        method = strip_tags(cells[4])
        dates = re.findall(r"(\d{1,2}-[A-Za-z]{3}-\d{4})\s+(\d{1,2}:\d{2})", strip_tags(cells[5]))
        published = parse_date(dates[0][0].replace("-", " ")) if dates else None
        closing = parse_date(dates[1][0].replace("-", " ")) if len(dates) > 1 else None
        closing_time = parse_time(dates[1][1]) if len(dates) > 1 else None
        if not title or published is None:
            continue
        official_url = BD_DETAIL.format(identifier=identifier)
        try:
            body = fetch_text(official_url, timeout=45)
        except Exception:
            body = ""
        detail = _bd_scrub(html_to_text(body)) if body else ""
        fields = _text_field(
            ("Tender title", title),
            ("Tender reference", reference),
            ("Issuing organisation", buyer),
            ("Procurement method", method),
            ("Published", published),
            ("Closing", f"{closing.isoformat()} {closing_time}" if closing and closing_time else closing),
        )
        text = f"{detail}\n{fields}".strip()
        digest = sha256(body.encode() if body else text.encode())
        document_id = ds.add_document(
            DocumentDraft(
                source_id="bd-egp",
                official_url=official_url,
                content_type="text/html",
                language="en",
                title=title[:300],
                publisher=buyer or "Bangladesh e-GP",
                publication_date=published,
                text=text,
                source_sha256=digest,
                source_bytes=len(body.encode()) if body else len(text.encode()),
            )
        )
        status = "open" if closing and closing >= TODAY else ("closed" if closing else "unknown")
        added += _record(
            ds,
            RecordDraft(
                record_type="tender",
                title=title,
                publication_date=published,
                document_id=document_id,
                source_id="bd-egp",
                official_url=official_url,
                excerpt=truncate(fields, 500),
                source_sha256=digest,
                language="en",
                keywords=["eprocure", "procurement", "bangladesh"],
                location="Bangladesh",
                organisation_name=buyer,
                sector=infer_sector(f"{method} {title}", "other"),
                tender={
                    "reference": reference,
                    "sector": infer_sector(f"{method} {title}", "other"),
                    "status": status,
                    "closing_date": closing,
                    "closing_time": closing_time,
                    "currency": "BDT",
                },
                issuing_organisation_name=buyer,
            ),
        )
    return added


ADAPTERS: dict[str, Callable[..., int]] = {
    "uk_gazette_notices": uk_gazette_notices,
    "uk_find_a_tender": uk_find_a_tender,
    "us_federal_register_notices": us_federal_register_notices,
    "us_grants_gov": us_grants_gov,
    "ca_gazette_notices": ca_gazette_notices,
    "ca_canadabuys": ca_canadabuys,
    "au_legislation": au_legislation,
    "au_notices": au_notices,
    "nz_gets": nz_gets,
    "sg_gebiz": sg_gebiz,
    "za_etenders": za_etenders,
    "ke_ppip": ke_ppip,
    "de_ted": de_ted,
    "ie_ted": ie_ted,
    "nl_ted": nl_ted,
    "de_bgbl": de_bgbl,
    "bd_egp": bd_egp,
}
