"""Generate the static GazetteRegistry site from validated local data."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from seo.breadcrumbs import Crumb, crumbs as make_crumbs
from seo.canonical import canonical_url
from seo.metadata import PageMetadata, excerpt, page_metadata
from seo.sitemap import SitemapBuilder
from seo.structured_data import (
    collection_page,
    organisation_page,
    profile_page,
    web_page,
    website,
)

from .loader import IssueBundle, SiteData, load_site
from .models import (
    SourceDocumentSnapshot,
    SourceRegistryEntry,
    CuratedRecord,
    GazettePage,
    NameVariant,
    OrganisationEntity,
    PersonEntity,
    PersonReference,
)

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
ASSETS = Path(__file__).resolve().parents[1] / "assets"

NAV = [
    {"label": "Home", "path": "/", "section": "home"},
    {"label": "Tenders", "path": "/tenders/", "section": "tenders", "header": True},
    {"label": "Gazettes", "path": "/gazettes/", "section": "gazettes", "header": True},
    {"label": "People", "path": "/people/", "section": "people", "header": True},
    {"label": "Organisations", "path": "/organisations/", "section": "organisations", "header": True},
    {"label": "Countries", "path": "/countries/", "section": "countries", "header": True},
    {"label": "Public notices", "path": "/notices/", "section": "notices"},
    {"label": "Regulations", "path": "/regulations/", "section": "regulations"},
    {"label": "Sources", "path": "/sources/", "section": "sources", "header": True},
    {"label": "About", "path": "/about/", "section": "about"},
]

RECORD_TYPE_LABELS = {
    "appointment": "Appointment",
    "commissioning": "Commissioning",
    "promotion": "Promotion",
    "professional_position": "Professional position",
    "organisational_appointment": "Organisational appointment",
    "tender": "Tender",
    "public_notice": "Public notice",
    "regulation": "Regulation",
}
RECORD_TYPE_TONES = {
    "appointment": "appointment",
    "commissioning": "appointment",
    "promotion": "appointment",
    "professional_position": "appointment",
    "organisational_appointment": "appointment",
    "tender": "tender",
    "public_notice": "notice",
    "regulation": "regulation",
}
SECTOR_LABELS = {
    "civil_works": "Civil works",
    "goods": "Goods and supplies",
    "consultancy": "Consultancy",
    "services": "Services",
    "it": "Information technology",
    "maintenance": "Maintenance",
    "auction": "Auction",
    "other": "Other",
}
NOTICE_LABELS = {
    "land": "Land",
    "insolvency": "Insolvency",
    "estate": "Estate",
    "court": "Court",
    "licensing": "Licensing",
    "professional": "Professional",
    "construction": "Construction",
    "infrastructure": "Infrastructure",
    "procurement": "Procurement notice",
    "technology": "Technology",
    "general": "General notice",
    "other": "Other",
}
OPPORTUNITY_KIND_LABELS = {
    "tender": "Tender",
    "grant": "Grant opportunity",
    "procurement_award": "Procurement award",
    "request_for_information": "Request for information",
    "market_consultation": "Market consultation",
    "other": "Other opportunity",
}
INSTRUMENT_LABELS = {
    "act": "Act",
    "regulation": "Regulation",
    "order": "Order",
    "rule": "Rule",
    "notification": "Notification",
    "by_law": "By-law",
    "other": "Other",
}
ORG_TYPE_LABELS = {
    "government_body": "Government body",
    "company": "Company",
    "professional_body": "Professional body",
    "statutory_body": "Statutory body",
    "other": "Other",
}


@dataclass
class BuildReport:
    output_dir: Path
    issues: int
    pages: int
    records: int
    people: int
    organisations: int
    html_files: int
    preview: bool
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OriginHeader:
    publication_date: date | None
    gazette_no: str


@dataclass(frozen=True)
class OriginSource:
    source_file: str
    sha256: str | None


@dataclass(frozen=True)
class RecordOrigin:
    """Uniform provenance view for PDF-gazette and international records."""

    country: CountryConfig
    issue: OriginHeader
    source: OriginSource
    path: str
    label: str
    kind: str
    official_url: str | None = None
    document: SourceDocumentSnapshot | None = None
    pdf_page: int | None = None
    printed_page: int | None = None
    registry_source: SourceRegistryEntry | None = None

    @property
    def is_pdf(self) -> bool:
        return self.document is None


def _date_long(value: date | str | None) -> str:
    if value is None:
        return "Not stated"
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return f"{value.day} {value.strftime('%B')} {value.year}"


def _date_long_or_missing(value: date | None) -> str:
    return _date_long(value) if value else "Not stated"


def _closing_state(closing_date: date | None) -> str:
    """Calculate the date-derived state independently of source-reported status."""
    if closing_date is None:
        return "unknown"
    return "closed" if closing_date < date.today() else "open"


def _effective_status(status: str, closing_date: date | None) -> str:
    """Presentation status that can never call an expired opportunity open.

    The stored source-reported status remains available separately.
    """
    if status in {"awarded", "cancelled", "closed"}:
        return status
    return _closing_state(closing_date)


def _opportunity_kind_label(value: str) -> str:
    return OPPORTUNITY_KIND_LABELS.get(value, value.replace("_", " ").title())


TENDER_STATUS_LABELS = {
    "open": "Open",
    "closed": "Closed",
    "awarded": "Awarded",
    "cancelled": "Cancelled",
    "unknown": "Status not stated",
}


def _tender_status_label(value: str) -> str:
    return TENDER_STATUS_LABELS.get(value, value.replace("_", " ").title())


def _tender_status_tone(value: str) -> str:
    if value == "open":
        return "verified"
    if value in {"closed", "cancelled"}:
        return "warning"
    return "neutral"


def _closing_note(closing_date: date | None) -> str:
    """Human closing-date label that never presents an expired date as current."""
    if closing_date is None:
        return "Date not stated"
    days = (closing_date - date.today()).days
    label = _date_long(closing_date)
    if days < 0:
        return f"Closed {label}"
    if days == 0:
        return f"{label} (today)"
    if days == 1:
        return f"{label} (tomorrow)"
    if days <= 30:
        return f"{label} (in {days} days)"
    return label


def _money(value: int) -> str:
    return f"{value:,}"


def _sector_label(value: str) -> str:
    return SECTOR_LABELS.get(value, value.replace("_", " ").title())


def _record_type_label(value: str) -> str:
    return RECORD_TYPE_LABELS.get(value, value.replace("_", " ").title())


def _record_path(record: CuratedRecord) -> str:
    if record.record_type == "tender":
        return f"/tenders/{record.uid}/"
    if record.record_type == "public_notice":
        return f"/notices/{record.uid}/"
    if record.record_type == "regulation":
        return f"/regulations/{record.uid}/"
    return f"/people/records/{record.uid}/"


def _person_path(person: PersonEntity) -> str:
    country, slug = person.person_id.split(":")[1], person.person_id.split(":", 2)[2]
    return f"/people/{country}/{slug}/"


def _org_path(org: OrganisationEntity) -> str:
    country, slug = org.organisation_id.split(":")[1], org.organisation_id.split(":", 2)[2]
    return f"/organisations/{country}/{slug}/"


def _page_path(page: GazettePage) -> str:
    return f"/records/{page.uid}/"


def _page_label(issue: IssueBundle, page: GazettePage) -> str:
    if page.printed_page:
        return f"Printed page {page.printed_page}"
    return f"PDF page {page.physical_pdf_page}"


def _record_official_url(site: SiteData, record: CuratedRecord) -> str | None:
    if record.source.kind != "pdf":
        return str(record.source.official_url) if record.source.official_url else None
    issue = site.issue_for(record.issue_id)
    source_url = record.source.official_url or issue.issue.source_url
    if not source_url:
        return None
    return f"{source_url}#page={record.source.pdf_page}"


def _registry_source(site: SiteData, source_id: str) -> SourceRegistryEntry | None:
    for entry in site.source_registry:
        if entry.source_id == source_id:
            return entry
    return None


def _origin(site: SiteData, record: CuratedRecord) -> RecordOrigin:
    country = site.country_of_record(record).config
    if record.source.kind == "pdf":
        issue = site.issue_for(record.issue_id)
        return RecordOrigin(
            country=country,
            issue=OriginHeader(issue.issue.publication_date, issue.issue.gazette_no),
            source=OriginSource(issue.source.source_file, issue.source.sha256),
            path=issue.path,
            label=f"Gazette No. {issue.issue.gazette_no}",
            kind="gazette",
            official_url=_record_official_url(site, record),
            pdf_page=record.source.pdf_page,
            printed_page=record.source.printed_page,
        )
    document = site.document_for(record.source.document_id or "")
    registry = _registry_source(site, document.source_id)
    publisher = document.publisher or (registry.organisation if registry else document.source_id)
    return RecordOrigin(
        country=country,
        issue=OriginHeader(record.publication_date or document.publication_date, publisher),
        source=OriginSource(f"document {document.document_id}", document.source_sha256),
        path=f"/sources/#source-{document.source_id}",
        label=registry.title if registry else publisher,
        kind=record.source.kind,
        official_url=str(record.source.official_url) if record.source.official_url else None,
        document=document,
        registry_source=registry,
    )


def _page_official_url(issue: IssueBundle, page: GazettePage) -> str | None:
    source_url = page.source.url or issue.issue.source_url
    if not source_url:
        return None
    return f"{source_url}#page={page.physical_pdf_page}"


def _record_issuer(site: SiteData, record: CuratedRecord) -> OrganisationEntity | None:
    if record.tender is None or record.tender.issuer_organisation_id is None:
        return None
    try:
        return site.organisation_for(record.tender.issuer_organisation_id)
    except KeyError:
        return None


def _record_orgs(site: SiteData, record: CuratedRecord) -> list[OrganisationEntity]:
    ids: list[str] = list(record.organisation_ids)
    for person in record.people:
        ids.extend(person.organisation_ids)
    if record.tender and record.tender.issuer_organisation_id:
        ids.append(record.tender.issuer_organisation_id)
    seen: set[str] = set()
    orgs: list[OrganisationEntity] = []
    for org_id in ids:
        if org_id in seen:
            continue
        seen.add(org_id)
        try:
            orgs.append(site.organisation_for(org_id))
        except KeyError:
            continue
    return orgs


def _latest_record_date(site: SiteData, records: list[CuratedRecord]) -> str | None:
    dates = [site.record_date(record) for record in records]
    dates = [value for value in dates if value is not None]
    return max(dates).isoformat() if dates else None


def _safe_json(value: str) -> Markup:
    return Markup(value)


def _build_env(site: SiteData) -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["date_long"] = _date_long
    env.filters["date_long_or_missing"] = _date_long_or_missing
    env.filters["money"] = _money
    env.globals.update(
        issue_for=site.issue_for,
        record_origin=lambda record: _origin(site, record),
        record_path=_record_path,
        person_path=_person_path,
        org_path=_org_path,
        page_path=_page_path,
        page_label=_page_label,
        record_type_label=_record_type_label,
        record_type_tone=lambda value: RECORD_TYPE_TONES.get(value, "neutral"),
        sector_label=_sector_label,
        opportunity_kind_label=_opportunity_kind_label,
        closing_state=_closing_state,
        effective_status=_effective_status,
        notice_category_label=lambda value: NOTICE_LABELS.get(value, value.title()),
        instrument_type_label=lambda value: INSTRUMENT_LABELS.get(value, value.title()),
        org_type_label=lambda value: ORG_TYPE_LABELS.get(value, value.title()),
        coverage_label=lambda value: {"verified": "Verified data", "partial": "Partial coverage", "planned": "Planned coverage"}.get(value, value.title()),
        coverage_tone=lambda value: {"verified": "verified", "partial": "warning", "planned": "neutral"}.get(value, "neutral"),
        access_status_label=lambda value: {"verified": "Accessible", "restricted": "Restricted", "unavailable": "Unavailable", "planned": "Planned"}.get(value, value.title()),
        person_reference_label=lambda ref: ref.published_name,
        record_source_url=lambda record: _record_official_url(site, record),
        record_count_for_issue=lambda issue_id: len(site.records_for_issue(issue_id)),
    )
    return env


def _write_page(
    env: Environment,
    output_dir: Path,
    path: str,
    template: str,
    *,
    meta: PageMetadata,
    crumbs: list[Crumb],
    structured_data: str,
    section: str,
    context: dict[str, Any],
    site: SiteData,
    pagefind_body: bool = True,
) -> None:
    canonical_path = path
    canonical = canonical_url(canonical_path, site.site_url)
    robots = meta.robots
    if site.preview:
        robots = "noindex,nofollow"
    page_meta = PageMetadata(meta.title, meta.description, robots, meta.og_type)
    html = env.get_template(template).render(
        site=site,
        nav=NAV,
        current_section=section,
        preview=site.preview,
        meta=page_meta,
        canonical=canonical,
        structured_data=_safe_json(structured_data),
        crumbs=crumbs,
        pagefind_body=pagefind_body,
        **context,
    )
    if path == "/":
        destination = output_dir / "index.html"
    elif path.endswith(".html"):
        destination = output_dir / path.lstrip("/")
    else:
        destination = output_dir / path.strip("/") / "index.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")


def _record_country_map(site: SiteData, records: list[CuratedRecord]) -> dict[str, str]:
    return {
        record.uid: site.country_of_record(record).config.country_code.lower()
        for record in records
    }


def _country_counts(country) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in country.records:
        counts[record.record_type] = counts.get(record.record_type, 0) + 1
    return counts


def _country_stat(site: SiteData, country) -> dict[str, Any]:
    counts = _country_counts(country)
    dates = [date for record in country.records if (date := site.record_date(record))]
    dates.extend(issue.issue.publication_date for issue in country.issues)
    sources = sorted(country.sources, key=lambda source: source.source_id)
    return {
        "country": country,
        "code": country.config.country_code,
        "name": country.config.name,
        "region": country.config.region,
        "coverage": country.config.coverage_status,
        "path": f"/countries/{country.config.country_code.lower()}/",
        "records": len(country.records),
        "tenders": counts.get("tender", 0),
        "notices": counts.get("public_notice", 0),
        "regulations": counts.get("regulation", 0),
        "appointments": sum(count for kind, count in counts.items() if kind not in {"tender", "public_notice", "regulation"}),
        "issues": len(country.issues),
        "pages": sum(len(issue.pages) for issue in country.issues),
        "documents": len(country.documents),
        "sources": len(sources),
        "verified_sources": sum(1 for source in sources if source.access_status == "verified"),
        "restricted_sources": sum(1 for source in sources if source.access_status in {"restricted", "unavailable"}),
        "source_rows": sources,
        "latest_date": max(dates) if dates else None,
        "languages": country.config.languages,
    }


def _home_context(site: SiteData) -> dict[str, Any]:
    counts = site.record_counts()
    country_stats = sorted(
        (_country_stat(site, country) for country in site.countries),
        key=lambda row: (row["region"], row["name"].casefold()),
    )
    # Balanced home: at most one lead record per country before any second record.
    latest_records: list[CuratedRecord] = []
    per_country = []
    for country in sorted(site.countries, key=lambda item: item.config.name.casefold()):
        dated = site.records_by_date(country.records)
        if dated:
            per_country.append(dated[0])
    latest_records = sorted(
        per_country,
        key=lambda record: (site.record_date(record) or date.min, record.uid),
        reverse=True,
    )[:6]
    latest_pages = []
    for issue in site.issues[:2]:
        for page in issue.pages[:2]:
            latest_pages.append(
                {
                    "issue": issue,
                    "page": page,
                    "excerpt": excerpt(issue.texts[page.uid], 220),
                }
            )

    tender_records = [
        record
        for record in site.records
        if record.record_type == "tender" and record.tender is not None
    ]
    open_tenders = [
        record
        for record in tender_records
        if _effective_status(record.tender.status, record.tender.closing_date) == "open"
    ]
    open_tenders.sort(
        key=lambda record: (
            record.tender.closing_date or date.max,
            -(site.record_date(record) or date.min).toordinal(),
            record.uid,
        )
    )
    spotlight_records = open_tenders[:4]
    if len(spotlight_records) < 4:
        remaining = sorted(
            (record for record in tender_records if record not in spotlight_records),
            key=lambda record: (
                site.record_date(record) or date.min,
                record.uid,
            ),
            reverse=True,
        )
        spotlight_records.extend(remaining[: 4 - len(spotlight_records)])

    latest_tenders = []
    for record in spotlight_records:
        issuer = _record_issuer(site, record)
        effective = _effective_status(record.tender.status, record.tender.closing_date)
        latest_tenders.append(
            {
                "record": record,
                "path": _record_path(record),
                "country_name": site.country_of_record(record).config.name,
                "issuer_name": issuer.name
                if issuer
                else (record.issuing_organisation_name or "Issuer not recorded"),
                "issuer_path": _org_path(issuer) if issuer else None,
                "status_label": _tender_status_label(effective),
                "status_tone": _tender_status_tone(effective),
                "closing_note": _closing_note(record.tender.closing_date),
                "reference": record.tender.reference,
            }
        )

    region_stats_by_name: dict[str, dict[str, Any]] = {}
    for row in country_stats:
        region = region_stats_by_name.setdefault(
            row["region"],
            {
                "name": row["region"],
                "countries": 0,
                "with_records": 0,
                "records": 0,
                "tenders": 0,
            },
        )
        region["countries"] += 1
        if row["records"]:
            region["with_records"] += 1
        region["records"] += row["records"]
        region["tenders"] += row["tenders"]
    region_stats = sorted(region_stats_by_name.values(), key=lambda row: row["name"].casefold())

    registry = site.source_registry
    registry_statuses = [entry.access_status for entry in registry]
    dates = [row["latest_date"] for row in country_stats if row["latest_date"]]
    return {
        "stats": {
            "issues": len(site.issues),
            "pages": site.page_record_count(),
            "records": len(site.records),
            "people": len(site.published_people),
            "organisations": len(site.organisations),
            "tenders": counts.get("tender", 0),
            "open_tenders": len(open_tenders),
            "notices": counts.get("public_notice", 0),
            "regulations": counts.get("regulation", 0),
            "countries": len(site.countries),
            "with_records": sum(1 for row in country_stats if row["records"]),
            "verified": sum(1 for row in country_stats if row["coverage"] == "verified"),
            "partial": sum(1 for row in country_stats if row["coverage"] == "partial"),
            "planned": sum(1 for row in country_stats if row["coverage"] == "planned"),
            "sources": len(registry),
            "sources_accessible": registry_statuses.count("verified"),
            "sources_restricted": registry_statuses.count("restricted")
            + registry_statuses.count("unavailable"),
            "sources_planned": registry_statuses.count("planned"),
        },
        "country_names": ", ".join(row["name"] for row in sorted(country_stats, key=lambda row: row["name"].casefold())),
        "country_stats": country_stats,
        "regions": sorted({row["region"] for row in country_stats}),
        "region_stats": region_stats,
        "latest_issue": site.issues[0] if site.issues else None,
        "latest_record_date": max(dates) if dates else None,
        "latest_records": latest_records,
        "latest_pages": latest_pages,
        "latest_tenders": latest_tenders,
    }


def build_site(
    *,
    data_root: Path,
    config_path: Path,
    output_dir: Path,
    raw_root: Path | None = None,
    preview: bool = False,
    site_url: str | None = None,
) -> BuildReport:
    site = load_site(
        data_root=data_root,
        config_path=config_path,
        raw_root=raw_root,
        preview=preview,
        site_url=site_url,
    )
    if output_dir.resolve() in {Path("/").resolve(), data_root.resolve()}:
        raise ValueError("Refusing to clean an unsafe output directory")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    shutil.copytree(ASSETS, output_dir / "assets")

    env = _build_env(site)
    sitemap = SitemapBuilder(site.site_url)
    home = _home_context(site)
    home_crumb = Crumb(site.config.site_name, "/")
    gazettes_crumb = Crumb("Gazettes", "/gazettes/")
    people_crumb = Crumb("People", "/people/")
    organisations_crumb = Crumb("Organisations", "/organisations/")
    countries_crumb = Crumb("Countries", "/countries/")
    sources_crumb = Crumb("Source registry", "/sources/")
    tenders_crumb = Crumb("Tenders", "/tenders/")
    notices_crumb = Crumb("Public notices", "/notices/")
    regulations_crumb = Crumb("Regulations", "/regulations/")
    about_crumb = Crumb("About", "/about/")
    corrections_crumb = Crumb("Corrections", "/corrections/")

    latest_date = max(
        [issue.issue.publication_date for issue in site.issues]
        + [value for record in site.records if (value := site.record_date(record))],
        default=None,
    )
    latest_iso = latest_date.isoformat() if latest_date else None

    # Home
    home_title = "Official Gazette, tender and public-record search"
    home_description = (
        f"Search official gazette, tender and appointment records from {home['stats']['with_records']} "
        f"countries: {home['stats']['records']} source-validated records, including "
        f"{home['stats']['tenders']} procurement records, with {home['stats']['issues']} indexed "
        f"Gazette issues and {home['stats']['pages']} searchable pages. Coverage is incomplete."
    )
    _write_page(
        env,
        output_dir,
        "/",
        "home.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title=home_title,
            description=home_description,
        ),
        crumbs=[home_crumb],
        structured_data=website(
            site_name=site.config.site_name,
            site_url=site.site_url,
            description=home_description,
        ),
        section="home",
        context=home,
        site=site,
    )
    sitemap.add("/", latest_iso)

    # Gazettes index
    countries_with_issues = [country for country in site.countries if country.issues]
    gazette_items = [(f"Gazette No. {issue.issue.gazette_no}", issue.path) for issue in site.issues]
    gazette_description = (
        f"Browse {len(site.issues)} indexed Gazette issues with {site.page_record_count()} searchable pages, "
        "source checksums and official document links where recorded."
    )
    _write_page(
        env,
        output_dir,
        "/gazettes/",
        "gazettes.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Gazette archive",
            description=gazette_description,
        ),
        crumbs=[home_crumb, gazettes_crumb],
        structured_data=collection_page(
            path="/gazettes/",
            title="Gazette archive",
            description=gazette_description,
            crumbs=[home_crumb, gazettes_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=gazette_items,
        ),
        section="gazettes",
        context={"countries_with_issues": countries_with_issues},
        site=site,
    )
    sitemap.add("/gazettes/", latest_iso)

    # Gazette issue and page records
    for issue in site.issues:
        issue_records = site.records_for_issue(issue.issue.issue_id)
        page_items = [
            {"page": page, "excerpt": excerpt(issue.texts[page.uid], 180)} for page in issue.pages
        ]
        issue_title = f"Gazette No. {issue.issue.gazette_no} ({_date_long(issue.issue.publication_date)})"
        issue_description = (
            f"{issue.country.name} Gazette No. {issue.issue.gazette_no}, published "
            f"{_date_long(issue.issue.publication_date)}. {len(issue.pages)} searchable pages, "
            f"{len(issue_records)} curated records and page-level source references."
        )
        _write_page(
            env,
            output_dir,
            issue.path,
            "issue.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=issue_title,
                description=issue_description,
            ),
            crumbs=[home_crumb, gazettes_crumb, Crumb(f"Gazette No. {issue.issue.gazette_no}", issue.path)],
            structured_data=collection_page(
                path=issue.path,
                title=issue_title,
                description=issue_description,
                crumbs=[home_crumb, gazettes_crumb, Crumb(f"Gazette No. {issue.issue.gazette_no}", issue.path)],
                site_name=site.config.site_name,
                site_url=site.site_url,
                items=[(_page_label(issue, page), _page_path(page)) for page in issue.pages],
            ),
            section="gazettes",
            context={"issue": issue, "records": issue_records, "page_items": page_items},
            site=site,
        )
        sitemap.add(issue.path, issue.issue.publication_date.isoformat())

        for page in issue.pages:
            text = issue.texts[page.uid]
            page_heading = f"Gazette No. {issue.issue.gazette_no} — {_page_label(issue, page).lower()}"
            page_path = _page_path(page)
            official_url = _page_official_url(issue, page)
            if official_url:
                source_detail = (
                    f'<a class="button button--small" href="{official_url}" target="_blank" rel="noopener">'
                    "Open official PDF <span aria-hidden=\"true\">↗</span></a>"
                )
            else:
                source_detail = '<span class="source-pending">Official PDF URL not recorded</span>'
            page_description = excerpt(
                f"Official {issue.country.name} Gazette No. {issue.issue.gazette_no}, "
                f"{_date_long(issue.issue.publication_date)}, {_page_label(issue, page).lower()}. {text}",
                155,
            )
            page_crumbs = [
                home_crumb,
                gazettes_crumb,
                Crumb(f"Gazette No. {issue.issue.gazette_no}", issue.path),
                Crumb(_page_label(issue, page), page_path),
            ]
            _write_page(
                env,
                output_dir,
                page_path,
                "record.html",
                meta=page_metadata(
                    site_name=site.config.site_name,
                    title=f"Gazette No. {issue.issue.gazette_no} — {_page_label(issue, page)}",
                    description=page_description,
                ),
                crumbs=page_crumbs,
                structured_data=web_page(
                    path=page_path,
                    title=f"Gazette No. {issue.issue.gazette_no} — {_page_label(issue, page)}",
                    description=page_description,
                    crumbs=page_crumbs,
                    site_name=site.config.site_name,
                    site_url=site.site_url,
                    citation=official_url,
                    date_published=issue.issue.publication_date.isoformat(),
                ),
                section="gazettes",
                context={
                    "issue": issue,
                    "page": page,
                    "page_heading": page_heading,
                    "text": text,
                    "source_url": official_url,
                    "record_source_link_detail": Markup(source_detail),
                },
                site=site,
            )
            sitemap.add(page_path, issue.issue.publication_date.isoformat())

    # People index
    person_cards = []
    for person in site.published_people:
        records = site.records_for_person(person.person_id)
        latest = None
        if records:
            record = records[0]
            ref = next(ref for ref in record.people if ref.person_id == person.person_id)
            latest = {
                "record": record,
                "origin": _origin(site, record),
                "position": ref.position,
                "organisations": [site.organisation_for(org_id) for org_id in ref.organisation_ids],
                "path": _record_path(record),
            }
        person_cards.append(
            {
                "person": person,
                "path": _person_path(person),
                "aliases": site.verified_variants_for(person.person_id),
                "record_count": len(records),
                "latest": latest,
            }
        )
    people_description = (
        f"{len(site.published_people)} operator-verified people with source-backed appointments, "
        "promotions and professional positions in indexed Gazettes."
    )
    _write_page(
        env,
        output_dir,
        "/people/",
        "people.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="People and official appointments",
            description=people_description,
        ),
        crumbs=[home_crumb, people_crumb],
        structured_data=collection_page(
            path="/people/",
            title="People and official appointments",
            description=people_description,
            crumbs=[home_crumb, people_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=[(card["person"].canonical_name, card["path"]) for card in person_cards],
        ),
        section="people",
        context={"person_cards": person_cards},
        site=site,
    )
    sitemap.add("/people/", latest_iso)

    for person in site.published_people:
        records = sorted(
            site.records_for_person(person.person_id),
            key=lambda record: (site.record_date(record) or date.min, record.uid),
        )
        history = []
        published_names: set[str] = set()
        for record in records:
            ref = next(ref for ref in record.people if ref.person_id == person.person_id)
            published_names.add(ref.published_name)
            history.append(
                {
                    "record": record,
                    "ref": ref,
                    "origin": _origin(site, record),
                    "organisations": [site.organisation_for(org_id) for org_id in ref.organisation_ids],
                    "path": _record_path(record),
                    "source_url": _record_official_url(site, record),
                }
            )
        path = _person_path(person)
        role_label = "appointments and positions"
        if history:
            latest = history[-1]
            bits = []
            if latest["ref"].position:
                bits.append(latest["ref"].position)
            if latest["organisations"]:
                organisation_name = latest["organisations"][0].name
                if organisation_name.casefold() not in (latest["ref"].position or "").casefold():
                    bits.append(f"at {organisation_name}")
            if bits:
                role_label = " ".join(bits)
        title = f"{person.canonical_name} — {role_label}"
        description = (
            f"Source-backed Gazette records linked to {person.canonical_name}. "
            f"{len(history)} record{'s' if len(history) != 1 else ''}, with Gazette number, publication date and page references."
        )
        person_crumbs = [home_crumb, people_crumb, Crumb(person.canonical_name, path)]
        _write_page(
            env,
            output_dir,
            path,
            "person.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=title,
                description=description,
                og_type="profile",
            ),
            crumbs=person_crumbs,
            structured_data=profile_page(
                path=path,
                title=title,
                description=description,
                crumbs=person_crumbs,
                site_name=site.config.site_name,
                site_url=site.site_url,
                person_name=person.canonical_name,
                alternate_names=[variant.name for variant in site.verified_variants_for(person.person_id)],
            ),
            section="people",
            context={
                "person": person,
                "aliases": site.verified_variants_for(person.person_id),
                "same_name": site.same_name_people(person),
                "history": history,
                "published_names": sorted(published_names),
            },
            site=site,
        )
        sitemap.add(path, _latest_record_date(site, records) or person.verified_at.isoformat() if person.verified_at else None)

    # Appointment, commissioning, promotion and professional-position records
    appointment_records = [
        record
        for record in site.records
        if record.record_type
        in {
            "appointment",
            "commissioning",
            "promotion",
            "professional_position",
            "organisational_appointment",
        }
    ]
    for record in appointment_records:
        origin = _origin(site, record)
        path = _record_path(record)
        people_items = []
        about_items: list[dict[str, Any]] = []
        for ref in record.people:
            try:
                person = site.person_for(ref.person_id)
            except KeyError:
                person = None
            person_path = (
                _person_path(person)
                if person is not None and person.identity_status == "operator_verified"
                else None
            )
            if person is not None and person_path:
                about_items.append({"@type": "Person", "name": person.canonical_name})
            people_items.append(
                {
                    "ref": ref,
                    "person": person,
                    "person_path": person_path,
                    "organisations": [
                        site.organisation_for(org_id) for org_id in ref.organisation_ids
                    ],
                }
            )
        related_orgs = _record_orgs(site, record)
        for org in related_orgs:
            about_items.append({"@type": "Organization", "name": org.name})
        title = f"{_record_type_label(record.record_type)}: {record.title}"
        description = (
            f"{_record_type_label(record.record_type)} published in {origin.label} "
            f"on {_date_long(origin.issue.publication_date)}."
        )
        record_crumbs = [home_crumb, people_crumb, Crumb(record.title, path)]
        _write_page(
            env,
            output_dir,
            path,
            "appointment.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=title,
                description=description,
                og_type="article",
            ),
            crumbs=record_crumbs,
            structured_data=web_page(
                path=path,
                title=title,
                description=description,
                crumbs=record_crumbs,
                site_name=site.config.site_name,
                site_url=site.site_url,
                about=about_items or None,
                citation=_record_official_url(site, record),
                date_published=origin.issue.publication_date.isoformat(),
            ),
            section="people",
            context={
                "record": record,
                "origin": origin,
                "people_items": people_items,
                "related_orgs": related_orgs,
            },
            site=site,
        )
        sitemap.add(path, origin.issue.publication_date.isoformat() if origin.issue.publication_date else "")

    # Organisations index
    org_cards = []
    for org in sorted(site.organisations, key=lambda item: item.name.casefold()):
        records = site.records_for_organisation(org.organisation_id)
        latest = None
        if records:
            record = records[0]
            latest = {
                "record": record,
                "origin": _origin(site, record),
                "path": _record_path(record),
            }
        org_cards.append(
            {
                "org": org,
                "path": _org_path(org),
                "record_count": len(records),
                "latest": latest,
            }
        )
    orgs_description = (
        f"{len(site.organisations)} organisations named in indexed Gazette records, with "
        "source-backed appointment, tender and notice references."
    )
    _write_page(
        env,
        output_dir,
        "/organisations/",
        "organisations.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Organisations in Gazette records",
            description=orgs_description,
        ),
        crumbs=[home_crumb, organisations_crumb],
        structured_data=collection_page(
            path="/organisations/",
            title="Organisations in Gazette records",
            description=orgs_description,
            crumbs=[home_crumb, organisations_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=[(card["org"].name, card["path"]) for card in org_cards],
        ),
        section="people",
        context={"org_cards": org_cards},
        site=site,
    )
    sitemap.add("/organisations/", latest_iso)

    for org in site.organisations:
        records = site.records_for_organisation(org.organisation_id)
        history = []
        for record in records:
            people = []
            for ref in record.people:
                try:
                    person = site.person_for(ref.person_id)
                    person_path = _person_path(person) if person.identity_status == "operator_verified" else None
                except KeyError:
                    person_path = None
                people.append(
                    {
                        "published_name": ref.published_name,
                        "position": ref.position,
                        "person_path": person_path,
                    }
                )
            history.append(
                {
                    "record": record,
                    "origin": _origin(site, record),
                    "people": people,
                    "tender_issuer": bool(
                        record.tender
                        and record.tender.issuer_organisation_id == org.organisation_id
                    ),
                    "path": _record_path(record),
                    "source_url": _record_official_url(site, record),
                }
            )
        path = _org_path(org)
        title = f"{org.name} — Gazette records"
        description = (
            f"Source-backed Gazette records naming {org.name}. "
            f"{len(history)} record{'s' if len(history) != 1 else ''} with official page references."
        )
        org_crumbs = [home_crumb, organisations_crumb, Crumb(org.name, path)]
        _write_page(
            env,
            output_dir,
            path,
            "organisation.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=title,
                description=description,
                robots="index,follow" if org.identity_status == "operator_verified" else "noindex,follow",
            ),
            crumbs=org_crumbs,
            structured_data=organisation_page(
                path=path,
                title=title,
                description=description,
                crumbs=org_crumbs,
                site_name=site.config.site_name,
                site_url=site.site_url,
                organisation_name=org.name,
                alternate_names=org.aliases,
            ),
            section="people",
            context={"org": org, "history": history},
            site=site,
        )
        if org.identity_status == "operator_verified":
            sitemap.add(path, _latest_record_date(site, records) or org.verified_at.isoformat() if org.verified_at else None)

    # Tenders index
    def _tender_sort(record: CuratedRecord) -> tuple[int, date, str]:
        status = _effective_status(record.tender.status, record.tender.closing_date)
        # Open opportunities first (soonest closing), then undated status,
        # then closed/awarded/cancelled records.
        priority = 0 if status == "open" else 1 if status == "unknown" else 2
        return (priority, record.tender.closing_date or date.max, record.uid)

    tender_records = sorted(
        [record for record in site.records if record.record_type == "tender"],
        key=_tender_sort,
    )
    tender_items = [
        {
            "record": record,
            "origin": _origin(site, record),
            "org": _record_issuer(site, record),
            "country": site.country_of_record(record).config,
            "closing_state": _closing_state(record.tender.closing_date),
            "effective_status": _effective_status(
                record.tender.status, record.tender.closing_date
            ),
        }
        for record in tender_records
    ]
    kind_values = sorted(
        {record.tender.opportunity_kind for record in tender_records},
        key=lambda value: _opportunity_kind_label(value),
    )
    sector_values = sorted(
        {record.tender.sector for record in tender_records},
        key=lambda value: SECTOR_LABELS.get(value, value),
    )
    location_values = sorted(
        {
            record.tender.location
            for record in tender_records
            if record.tender.location
        }
    )
    organisation_values = sorted(
        {
            (record.tender.issuer_organisation_id, org.name)
            for record in tender_records
            if record.tender.issuer_organisation_id
            for org in [_record_issuer(site, record)]
            if org is not None
        },
        key=lambda pair: pair[1].casefold(),
    )
    tender_description = (
        f"{len(tender_records)} supplier opportunities published in indexed Gazettes. "
        "Filter by industry, location, issuing organisation and closing date, with official source references."
    )
    _write_page(
        env,
        output_dir,
        "/tenders/",
        "tenders.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Tenders and supplier opportunities",
            description=tender_description,
        ),
        crumbs=[home_crumb, tenders_crumb],
        structured_data=collection_page(
            path="/tenders/",
            title="Tenders and supplier opportunities",
            description=tender_description,
            crumbs=[home_crumb, tenders_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=[(item["record"].title, _record_path(item["record"])) for item in tender_items],
        ),
        section="tenders",
        context={
            "tenders": tender_items,
            "kind_options": [(value, _opportunity_kind_label(value)) for value in kind_values],
            "sector_options": [(value, _sector_label(value)) for value in sector_values],
            "location_options": location_values,
            "organisation_options": organisation_values,
            "country_options": [
                (country.config.country_code.lower(), country.config.name)
                for country in sorted(site.countries, key=lambda item: item.config.name.casefold())
                if any(record for record in country.records if record.record_type == "tender")
            ],
        },
        site=site,
    )
    sitemap.add("/tenders/", latest_iso)

    for record in tender_records:
        origin = _origin(site, record)
        issuer = _record_issuer(site, record)
        related_orgs = _record_orgs(site, record)
        path = _record_path(record)
        title = f"Tender {record.tender.reference}: {record.title}"
        description = (
            f"Tender {record.tender.reference} published in {origin.label} on "
            f"{_date_long(origin.issue.publication_date)}. Issuer: {issuer.name if issuer else 'not recorded'}. "
            f"Closing: {_date_long_or_missing(record.tender.closing_date)}."
        )
        record_crumbs = [home_crumb, tenders_crumb, Crumb(record.title, path)]
        about = (
            {"@type": "Organization", "name": issuer.name}
            if issuer
            else None
        )
        _write_page(
            env,
            output_dir,
            path,
            "tender.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=title,
                description=description,
                og_type="article",
            ),
            crumbs=record_crumbs,
            structured_data=web_page(
                path=path,
                title=title,
                description=description,
                crumbs=record_crumbs,
                site_name=site.config.site_name,
                site_url=site.site_url,
                about=about,
                citation=_record_official_url(site, record),
                date_published=origin.issue.publication_date.isoformat(),
            ),
            section="tenders",
            context={
                "record": record,
                "origin": origin,
                "issuer": issuer,
                "related_orgs": related_orgs,
                "closing_state": _closing_state(record.tender.closing_date),
                "effective_status": _effective_status(
                    record.tender.status, record.tender.closing_date
                ),
            },
            site=site,
        )
        sitemap.add(path, origin.issue.publication_date.isoformat() if origin.issue.publication_date else "")

    # Public notices
    notices = site.records_by_date(
        [record for record in site.records if record.record_type == "public_notice"]
    )
    notice_description = (
        f"{len(notices)} land, insolvency, estate, court and licensing notices from indexed Gazettes, "
        "with exact source page references."
    )
    _write_page(
        env,
        output_dir,
        "/notices/",
        "notices.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Public notices",
            description=notice_description,
        ),
        crumbs=[home_crumb, notices_crumb],
        structured_data=collection_page(
            path="/notices/",
            title="Public notices",
            description=notice_description,
            crumbs=[home_crumb, notices_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=[(record.title, _record_path(record)) for record in notices],
        ),
        section="notices",
        context={
            "notices": notices,
            "country_options": [
                (country.config.country_code.lower(), country.config.name)
                for country in sorted(site.countries, key=lambda item: item.config.name.casefold())
                if any(record for record in country.records if record.record_type == "public_notice")
            ],
            "record_country": _record_country_map(site, notices),
        },
        site=site,
    )
    sitemap.add("/notices/", latest_iso)

    for record in notices:
        origin = _origin(site, record)
        path = _record_path(record)
        related_orgs = _record_orgs(site, record)
        related_people = []
        for ref in record.people:
            try:
                person = site.person_for(ref.person_id)
                person_path = _person_path(person) if person.identity_status == "operator_verified" else None
            except KeyError:
                person_path = None
            related_people.append({"published_name": ref.published_name, "person_path": person_path})
        title = f"Public notice: {record.title}"
        description = (
            f"{NOTICE_LABELS.get(record.notice.category, 'Public')} notice published in Gazette No. "
            f"{origin.issue.gazette_no} on {_date_long(origin.issue.publication_date)}."
        )
        record_crumbs = [home_crumb, notices_crumb, Crumb(record.title, path)]
        _write_page(
            env,
            output_dir,
            path,
            "notice.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=title,
                description=description,
                og_type="article",
            ),
            crumbs=record_crumbs,
            structured_data=web_page(
                path=path,
                title=title,
                description=description,
                crumbs=record_crumbs,
                site_name=site.config.site_name,
                site_url=site.site_url,
                citation=_record_official_url(site, record),
                date_published=origin.issue.publication_date.isoformat(),
            ),
            section="notices",
            context={
                "record": record,
                "origin": origin,
                "related_orgs": related_orgs,
                "related_people": related_people,
            },
            site=site,
        )
        sitemap.add(path, origin.issue.publication_date.isoformat() if origin.issue.publication_date else "")

    # Regulations
    regulations = site.records_by_date(
        [record for record in site.records if record.record_type == "regulation"]
    )
    regulation_description = (
        f"{len(regulations)} Acts, regulations, orders, rules and notifications from indexed Gazettes, "
        "linked to their official source page."
    )
    _write_page(
        env,
        output_dir,
        "/regulations/",
        "regulations.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Regulations and instruments",
            description=regulation_description,
        ),
        crumbs=[home_crumb, regulations_crumb],
        structured_data=collection_page(
            path="/regulations/",
            title="Regulations and instruments",
            description=regulation_description,
            crumbs=[home_crumb, regulations_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=[(record.title, _record_path(record)) for record in regulations],
        ),
        section="regulations",
        context={
            "regulations": regulations,
            "country_options": [
                (country.config.country_code.lower(), country.config.name)
                for country in sorted(site.countries, key=lambda item: item.config.name.casefold())
                if any(record for record in country.records if record.record_type == "regulation")
            ],
            "record_country": _record_country_map(site, regulations),
        },
        site=site,
    )
    sitemap.add("/regulations/", latest_iso)

    for record in regulations:
        origin = _origin(site, record)
        path = _record_path(record)
        related_orgs = _record_orgs(site, record)
        title = f"Regulation: {record.title}"
        description = (
            f"{INSTRUMENT_LABELS.get(record.regulation.instrument_type, 'Instrument')} published in "
            f"{origin.label} on {_date_long(origin.issue.publication_date)}."
        )
        record_crumbs = [home_crumb, regulations_crumb, Crumb(record.title, path)]
        _write_page(
            env,
            output_dir,
            path,
            "regulation.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=title,
                description=description,
                og_type="article",
            ),
            crumbs=record_crumbs,
            structured_data=web_page(
                path=path,
                title=title,
                description=description,
                crumbs=record_crumbs,
                site_name=site.config.site_name,
                site_url=site.site_url,
                citation=_record_official_url(site, record),
                date_published=origin.issue.publication_date.isoformat(),
            ),
            section="regulations",
            context={"record": record, "origin": origin, "related_orgs": related_orgs},
            site=site,
        )
        sitemap.add(path, origin.issue.publication_date.isoformat() if origin.issue.publication_date else "")

    # Countries index and country coverage pages
    country_stats = home["country_stats"]
    country_description = (
        f"Alphabetical and regional coverage across {len(country_stats)} countries, distinguishing "
        "verified data, partial coverage and planned coverage."
    )
    _write_page(
        env,
        output_dir,
        "/countries/",
        "countries.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Country coverage",
            description=country_description,
        ),
        crumbs=[home_crumb, countries_crumb],
        structured_data=collection_page(
            path="/countries/",
            title="Country coverage",
            description=country_description,
            crumbs=[home_crumb, countries_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=[(row["name"], row["path"]) for row in sorted(country_stats, key=lambda row: row["name"].casefold())],
        ),
        section="countries",
        context={
            "country_stats": country_stats,
            "regions": home["regions"],
            "stats": home["stats"],
        },
        site=site,
    )
    sitemap.add("/countries/", latest_iso)

    for row in country_stats:
        country = row["country"]
        recent = site.records_by_date(country.records)[:8]
        country_path = row["path"]
        ctitle = f"{row['name']} — official records and procurement"
        cdesc = (
            f"{row['records']} curated records and {row['sources']} registered official sources "
            f"for {row['name']}. Coverage status: {row['coverage']}."
        )
        ccrumbs = [home_crumb, countries_crumb, Crumb(row["name"], country_path)]
        _write_page(
            env,
            output_dir,
            country_path,
            "country.html",
            meta=page_metadata(
                site_name=site.config.site_name,
                title=ctitle,
                description=cdesc,
            ),
            crumbs=ccrumbs,
            structured_data=collection_page(
                path=country_path,
                title=ctitle,
                description=cdesc,
                crumbs=ccrumbs,
                site_name=site.config.site_name,
                site_url=site.site_url,
                items=[(record.title, _record_path(record)) for record in recent],
            ),
            section="countries",
            context={"row": row, "recent_records": recent},
            site=site,
        )
        sitemap.add(country_path, row["latest_date"].isoformat() if row["latest_date"] else None)

    # Source registry
    country_by_code = {
        country.config.country_code: country.config.name for country in site.countries
    }
    source_items = []
    for entry in sorted(
        site.source_registry,
        key=lambda item: (country_by_code.get(item.country_code, item.country_code), item.title.casefold()),
    ):
        source_items.append(
            {
                "source": entry,
                "country_code": entry.country_code,
                "country_name": country_by_code.get(entry.country_code, entry.country_code),
            }
        )
    sources_description = (
        f"{len(source_items)} official gazette, public-notice, legislation and procurement sources "
        "across the indexed countries, including restricted and unavailable publishers."
    )
    _write_page(
        env,
        output_dir,
        "/sources/",
        "sources.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Official source registry",
            description=sources_description,
        ),
        crumbs=[home_crumb, sources_crumb],
        structured_data=collection_page(
            path="/sources/",
            title="Official source registry",
            description=sources_description,
            crumbs=[home_crumb, sources_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
            items=[(item["source"].title, f"/sources/#source-{item['source'].source_id}") for item in source_items],
        ),
        section="sources",
        context={
            "sources": source_items,
            "country_stats": country_stats,
            "stats": home["stats"],
        },
        site=site,
    )
    sitemap.add("/sources/", latest_iso)

    # About and corrections
    about_description = (
        f"About {site.config.site_name}: independent Gazette indexing, source provenance, identity policy and limitations."
    )
    _write_page(
        env,
        output_dir,
        "/about/",
        "about.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="About the index",
            description=about_description,
        ),
        crumbs=[home_crumb, about_crumb],
        structured_data=web_page(
            path="/about/",
            title="About the index",
            description=about_description,
            crumbs=[home_crumb, about_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
        ),
        section="about",
        context={**home, "country_names": ", ".join(country.config.name for country in site.countries)},
        site=site,
    )
    sitemap.add("/about/", latest_iso)

    corrections_description = (
        "How to request a correction to an indexed record, source link, transcription or identity mapping."
    )
    _write_page(
        env,
        output_dir,
        "/corrections/",
        "corrections.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Request a correction",
            description=corrections_description,
        ),
        crumbs=[home_crumb, corrections_crumb],
        structured_data=web_page(
            path="/corrections/",
            title="Request a correction",
            description=corrections_description,
            crumbs=[home_crumb, corrections_crumb],
            site_name=site.config.site_name,
            site_url=site.site_url,
        ),
        section="about",
        context={"corrections": True},
        site=site,
    )
    sitemap.add("/corrections/", latest_iso)

    # Static 404
    not_found_description = "The requested page was not found."
    _write_page(
        env,
        output_dir,
        "/404.html",
        "404.html",
        meta=page_metadata(
            site_name=site.config.site_name,
            title="Page not found",
            description=not_found_description,
            robots="noindex,nofollow",
        ),
        crumbs=[home_crumb, Crumb("Page not found", "/404.html")],
        structured_data=web_page(
            path="/404.html",
            title="Page not found",
            description=not_found_description,
            crumbs=[home_crumb, Crumb("Page not found", "/404.html")],
            site_name=site.config.site_name,
            site_url=site.site_url,
        ),
        section="",
        context={},
        site=site,
        pagefind_body=False,
    )

    # Deployment metadata
    if not site.preview:
        sitemap.write(output_dir / "sitemap.xml")
        robots = f"User-agent: *\nAllow: /\nSitemap: {canonical_url('/sitemap.xml', site.site_url)}\n"
        (output_dir / "robots.txt").write_text(robots, encoding="utf-8")
        host = urlsplit(site.site_url).hostname
        if host and not host.endswith("github.io") and host != "preview.invalid":
            (output_dir / "CNAME").write_text(f"{host}\n", encoding="utf-8")
    else:
        (output_dir / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")

    headers = [
        "/*",
        "  X-Content-Type-Options: nosniff",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "  Permissions-Policy: geolocation=(), camera=(), microphone=()",
        "  X-Frame-Options: SAMEORIGIN",
    ]
    if site.preview:
        headers.append("  X-Robots-Tag: noindex, nofollow")
    (output_dir / "_headers").write_text("\n".join(headers) + "\n", encoding="utf-8")

    html_files = sum(1 for _ in output_dir.rglob("*.html"))
    return BuildReport(
        output_dir=output_dir,
        issues=len(site.issues),
        pages=site.page_record_count(),
        records=len(site.records),
        people=len(site.published_people),
        organisations=len(site.organisations),
        html_files=html_files,
        preview=site.preview,
        warnings=site.warnings,
    )
