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
    {"label": "Gazettes", "path": "/gazettes/", "section": "gazettes"},
    {"label": "People & Organisations", "path": "/people/", "section": "people"},
    {"label": "Tenders", "path": "/tenders/", "section": "tenders"},
    {"label": "Public Notices", "path": "/notices/", "section": "notices"},
    {"label": "Regulations", "path": "/regulations/", "section": "regulations"},
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
    "other": "Other",
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
    issue = site.issue_for(record.issue_id)
    source_url = record.source.official_url or issue.issue.source_url
    if not source_url:
        return None
    return f"{source_url}#page={record.source.pdf_page}"


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
    dates = [site.issue_for(record.issue_id).issue.publication_date for record in records]
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
        record_path=_record_path,
        person_path=_person_path,
        org_path=_org_path,
        page_path=_page_path,
        page_label=_page_label,
        record_type_label=_record_type_label,
        record_type_tone=lambda value: RECORD_TYPE_TONES.get(value, "neutral"),
        sector_label=_sector_label,
        notice_category_label=lambda value: NOTICE_LABELS.get(value, value.title()),
        instrument_type_label=lambda value: INSTRUMENT_LABELS.get(value, value.title()),
        org_type_label=lambda value: ORG_TYPE_LABELS.get(value, value.title()),
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


def _home_context(site: SiteData) -> dict[str, Any]:
    counts = site.record_counts()
    latest_records = sorted(
        site.records,
        key=lambda record: site.issue_for(record.issue_id).issue.publication_date,
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
    return {
        "stats": {
            "issues": len(site.issues),
            "pages": site.page_record_count(),
            "records": len(site.records),
            "people": len(site.published_people),
            "organisations": len(site.organisations),
            "tenders": counts.get("tender", 0),
            "notices": counts.get("public_notice", 0),
            "regulations": counts.get("regulation", 0),
            "countries": len(site.countries),
        },
        "country_names": ", ".join(country.config.name for country in site.countries),
        "latest_issue": site.issues[0] if site.issues else None,
        "latest_records": latest_records,
        "latest_pages": latest_pages,
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
    tenders_crumb = Crumb("Tenders", "/tenders/")
    notices_crumb = Crumb("Public notices", "/notices/")
    regulations_crumb = Crumb("Regulations", "/regulations/")
    about_crumb = Crumb("About", "/about/")
    corrections_crumb = Crumb("Corrections", "/corrections/")

    latest_date = max((issue.issue.publication_date for issue in site.issues), default=None)
    latest_iso = latest_date.isoformat() if latest_date else None

    # Home
    home_title = "Search official Gazette records"
    home_description = (
        f"Search {home['stats']['pages']} indexed pages across {home['stats']['issues']} official "
        f"Gazette issues in {home['country_names']}. Appointments, tenders, public notices and regulations."
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
                "issue": site.issue_for(record.issue_id),
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
        records = site.records_for_person(person.person_id)
        history = []
        published_names: set[str] = set()
        for record in records:
            ref = next(ref for ref in record.people if ref.person_id == person.person_id)
            published_names.add(ref.published_name)
            history.append(
                {
                    "record": record,
                    "ref": ref,
                    "issue": site.issue_for(record.issue_id),
                    "organisations": [site.organisation_for(org_id) for org_id in ref.organisation_ids],
                    "path": _record_path(record),
                    "source_url": _record_official_url(site, record),
                }
            )
        path = _person_path(person)
        role_label = "appointments and positions"
        if history:
            latest = history[0]
            bits = []
            if latest["ref"].position:
                bits.append(latest["ref"].position)
            if latest["organisations"]:
                bits.append(f"at {latest['organisations'][0].name}")
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
        issue = site.issue_for(record.issue_id)
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
            f"{_record_type_label(record.record_type)} published in Gazette No. {issue.issue.gazette_no} "
            f"on {_date_long(issue.issue.publication_date)}."
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
                date_published=issue.issue.publication_date.isoformat(),
            ),
            section="people",
            context={
                "record": record,
                "issue": issue,
                "people_items": people_items,
                "related_orgs": related_orgs,
            },
            site=site,
        )
        sitemap.add(path, issue.issue.publication_date.isoformat())

    # Organisations index
    org_cards = []
    for org in sorted(site.organisations, key=lambda item: item.name.casefold()):
        records = site.records_for_organisation(org.organisation_id)
        latest = None
        if records:
            record = records[0]
            latest = {
                "record": record,
                "issue": site.issue_for(record.issue_id),
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
                    "issue": site.issue_for(record.issue_id),
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
    tender_records = sorted(
        [record for record in site.records if record.record_type == "tender"],
        key=lambda record: (
            record.tender.closing_date is None,
            record.tender.closing_date or date.max,
            record.uid,
        ),
    )
    tender_items = [
        {
            "record": record,
            "issue": site.issue_for(record.issue_id),
            "org": _record_issuer(site, record),
        }
        for record in tender_records
    ]
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
            "sector_options": [(value, _sector_label(value)) for value in sector_values],
            "location_options": location_values,
            "organisation_options": organisation_values,
        },
        site=site,
    )
    sitemap.add("/tenders/", latest_iso)

    for record in tender_records:
        issue = site.issue_for(record.issue_id)
        issuer = _record_issuer(site, record)
        related_orgs = _record_orgs(site, record)
        path = _record_path(record)
        title = f"Tender {record.tender.reference}: {record.title}"
        description = (
            f"Tender {record.tender.reference} published in Gazette No. {issue.issue.gazette_no} on "
            f"{_date_long(issue.issue.publication_date)}. Issuer: {issuer.name if issuer else 'not recorded'}. "
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
                date_published=issue.issue.publication_date.isoformat(),
            ),
            section="tenders",
            context={"record": record, "issue": issue, "issuer": issuer, "related_orgs": related_orgs},
            site=site,
        )
        sitemap.add(path, issue.issue.publication_date.isoformat())

    # Public notices
    notices = sorted(
        [record for record in site.records if record.record_type == "public_notice"],
        key=lambda record: site.issue_for(record.issue_id).issue.publication_date,
        reverse=True,
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
        context={"notices": notices},
        site=site,
    )
    sitemap.add("/notices/", latest_iso)

    for record in notices:
        issue = site.issue_for(record.issue_id)
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
            f"{issue.issue.gazette_no} on {_date_long(issue.issue.publication_date)}."
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
                date_published=issue.issue.publication_date.isoformat(),
            ),
            section="notices",
            context={
                "record": record,
                "issue": issue,
                "related_orgs": related_orgs,
                "related_people": related_people,
            },
            site=site,
        )
        sitemap.add(path, issue.issue.publication_date.isoformat())

    # Regulations
    regulations = sorted(
        [record for record in site.records if record.record_type == "regulation"],
        key=lambda record: site.issue_for(record.issue_id).issue.publication_date,
        reverse=True,
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
        context={"regulations": regulations},
        site=site,
    )
    sitemap.add("/regulations/", latest_iso)

    for record in regulations:
        issue = site.issue_for(record.issue_id)
        path = _record_path(record)
        related_orgs = _record_orgs(site, record)
        title = f"Regulation: {record.title}"
        description = (
            f"{INSTRUMENT_LABELS.get(record.regulation.instrument_type, 'Instrument')} published in "
            f"Gazette No. {issue.issue.gazette_no} on {_date_long(issue.issue.publication_date)}."
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
                date_published=issue.issue.publication_date.isoformat(),
            ),
            section="regulations",
            context={"record": record, "issue": issue, "related_orgs": related_orgs},
            site=site,
        )
        sitemap.add(path, issue.issue.publication_date.isoformat())

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
