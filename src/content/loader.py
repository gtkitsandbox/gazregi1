"""Load and validate the file-backed GazetteRegistry dataset.

The loader is deliberately storage-agnostic at its edges: it reads local
NDJSON/JSON/GZIP files today, and the same validated objects could be fed by an
R2 adapter later without changing page generation.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from .models import (
    RECORD_TYPE_CATEGORY,
    CountryConfig,
    CuratedRecord,
    GazetteIssue,
    GazettePage,
    NameVariant,
    OrganisationEntity,
    PersonEntity,
    PersonReference,
    SiteConfig,
    SourceDocument,
    SourceDocumentSnapshot,
    SourceRegistryEntry,
    normalise_name,
    normalise_text,
)

T = TypeVar("T", bound=BaseModel)


class ContentValidationError(Exception):
    """Raised when the local dataset cannot be published safely."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} content validation error(s):\n" + "\n".join(errors))


@dataclass(frozen=True)
class IssueBundle:
    issue: GazetteIssue
    country: CountryConfig
    pages: tuple[GazettePage, ...]
    texts: dict[str, str]
    source: SourceDocument

    @property
    def path(self) -> str:
        return f"/gazettes/{self.issue.issue_id}/"

    def page(self, physical_page: int) -> GazettePage:
        for page in self.pages:
            if page.physical_pdf_page == physical_page:
                return page
        raise KeyError(f"{self.issue.issue_id} has no PDF page {physical_page}")


@dataclass
class CountryData:
    config: CountryConfig
    issues: list[IssueBundle] = field(default_factory=list)
    records: list[CuratedRecord] = field(default_factory=list)
    people: list[PersonEntity] = field(default_factory=list)
    organisations: list[OrganisationEntity] = field(default_factory=list)
    variants: list[NameVariant] = field(default_factory=list)
    documents: list[SourceDocumentSnapshot] = field(default_factory=list)
    sources: list[SourceRegistryEntry] = field(default_factory=list)

    def record_date(self, record: CuratedRecord) -> date | None:
        if record.publication_date is not None:
            return record.publication_date
        for bundle in self.issues:
            if bundle.issue.issue_id == record.issue_id:
                return bundle.issue.publication_date
        return None


@dataclass
class SiteData:
    config: SiteConfig
    site_url: str
    preview: bool
    countries: list[CountryData]
    warnings: list[str] = field(default_factory=list)

    @property
    def issues(self) -> list[IssueBundle]:
        return sorted(
            (issue for country in self.countries for issue in country.issues),
            key=lambda bundle: (bundle.issue.publication_date, bundle.issue.issue_id),
            reverse=True,
        )

    @property
    def pages(self) -> list[tuple[IssueBundle, GazettePage]]:
        return [
            (issue, page)
            for issue in sorted(
                self.issues, key=lambda bundle: (bundle.issue.publication_date, bundle.issue.issue_id)
            )
            for page in issue.pages
        ]

    @property
    def records(self) -> list[CuratedRecord]:
        return [record for country in self.countries for record in country.records]

    @property
    def people(self) -> list[PersonEntity]:
        return [person for country in self.countries for person in country.people]

    @property
    def organisations(self) -> list[OrganisationEntity]:
        return [org for country in self.countries for org in country.organisations]

    @property
    def variants(self) -> list[NameVariant]:
        return [variant for country in self.countries for variant in country.variants]

    @property
    def documents(self) -> list[SourceDocumentSnapshot]:
        return [document for country in self.countries for document in country.documents]

    @property
    def source_registry(self) -> list[SourceRegistryEntry]:
        return [source for country in self.countries for source in country.sources]

    @property
    def published_people(self) -> list[PersonEntity]:
        return sorted(
            (person for person in self.people if person.identity_status == "operator_verified"),
            key=lambda person: person.canonical_name.casefold(),
        )

    @property
    def published_organisations(self) -> list[OrganisationEntity]:
        return sorted(
            (org for org in self.organisations if org.identity_status == "operator_verified"),
            key=lambda org: org.name.casefold(),
        )

    @property
    def held_people(self) -> list[PersonEntity]:
        return [person for person in self.people if person.identity_status != "operator_verified"]

    def country_for(self, country_code: str) -> CountryData:
        for country in self.countries:
            if country.config.country_code == country_code:
                return country
        raise KeyError(country_code)

    def issue_for(self, issue_id: str) -> IssueBundle:
        for issue in self.issues:
            if issue.issue.issue_id == issue_id:
                return issue
        raise KeyError(issue_id)

    def record_for(self, uid: str) -> CuratedRecord:
        for record in self.records:
            if record.uid == uid:
                return record
        raise KeyError(uid)

    def country_of_record(self, record: CuratedRecord) -> CountryData:
        for country in self.countries:
            if record in country.records:
                return country
        raise KeyError(record.uid)

    def record_date(self, record: CuratedRecord) -> date | None:
        return self.country_of_record(record).record_date(record)

    def document_for(self, document_id: str) -> SourceDocumentSnapshot:
        for document in self.documents:
            if document.document_id == document_id:
                return document
        raise KeyError(document_id)

    def records_by_date(self, records: list[CuratedRecord]) -> list[CuratedRecord]:
        return sorted(
            records,
            key=lambda record: (self.record_date(record) or date.min, record.uid),
            reverse=True,
        )

    def person_for(self, person_id: str) -> PersonEntity:
        for person in self.people:
            if person.person_id == person_id:
                return person
        raise KeyError(person_id)

    def organisation_for(self, org_id: str) -> OrganisationEntity:
        for org in self.organisations:
            if org.organisation_id == org_id:
                return org
        raise KeyError(org_id)

    def records_for_person(self, person_id: str) -> list[CuratedRecord]:
        rows = [
            record
            for record in self.records
            if any(person.person_id == person_id for person in record.people)
        ]
        return self.records_by_date(rows)

    def records_for_organisation(self, org_id: str) -> list[CuratedRecord]:
        rows = []
        for record in self.records:
            linked = org_id in record.organisation_ids
            linked = linked or any(org_id in person.organisation_ids for person in record.people)
            linked = linked or (record.tender is not None and record.tender.issuer_organisation_id == org_id)
            if linked:
                rows.append(record)
        return self.records_by_date(rows)

    def records_for_issue(self, issue_id: str) -> list[CuratedRecord]:
        rows = [record for record in self.records if record.issue_id == issue_id]
        return sorted(rows, key=lambda record: (record.source.pdf_page or 0, record.uid))

    def verified_variants_for(self, person_id: str) -> list[NameVariant]:
        return sorted(
            (
                variant
                for variant in self.variants
                if variant.person_id == person_id and variant.verification == "operator_verified"
            ),
            key=lambda variant: variant.name.casefold(),
        )

    def same_name_people(self, person: PersonEntity) -> list[PersonEntity]:
        """Return other verified people sharing a published/verified name.

        Used only for disambiguation links.  It never merges identities.
        """
        names = {normalise_name(person.canonical_name)}
        names.update(normalise_name(variant.name) for variant in self.verified_variants_for(person.person_id))
        matches: list[PersonEntity] = []
        for other in self.published_people:
            if other.person_id == person.person_id:
                continue
            other_names = {normalise_name(other.canonical_name)}
            other_names.update(
                normalise_name(variant.name) for variant in self.verified_variants_for(other.person_id)
            )
            if names & other_names:
                matches.append(other)
        return matches

    def page_record_count(self) -> int:
        return sum(len(issue.pages) for issue in self.issues)

    def record_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.record_type] = counts.get(record.record_type, 0) + 1
        return counts


def _load_model(path: Path, model: type[T]) -> T:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise ContentValidationError([f"{path}: {exc}"]) from exc
    except json.JSONDecodeError as exc:
        raise ContentValidationError([f"{path}: invalid JSON: {exc}"]) from exc


def _load_ndjson(path: Path, model: type[T], errors: list[str]) -> list[T]:
    if not path.exists():
        return []
    rows: list[T] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(model.model_validate_json(line))
        except ValidationError as exc:
            errors.append(f"{path}:{line_number}: {exc}")
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc}")
    return rows


def _read_texts(path: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                record = json.loads(line)
                texts[record["uid"]] = record["text"]
    return texts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_site(
    *,
    data_root: Path,
    config_path: Path,
    raw_root: Path | None = None,
    preview: bool = False,
    site_url: str | None = None,
) -> SiteData:
    errors: list[str] = []
    warnings: list[str] = []
    config = _load_model(config_path, SiteConfig)
    if preview:
        site_url = site_url or "https://preview.invalid"
    else:
        site_url = (site_url or config.default_site_url).rstrip("/")

    countries: list[CountryData] = []
    seen_issue_ids: set[str] = set()
    seen_page_uids: set[str] = set()
    seen_record_uids: set[str] = set()
    seen_person_ids: set[str] = set()
    seen_org_ids: set[str] = set()

    for country_code in config.countries:
        country_dir = data_root / country_code.lower()
        country_config_path = country_dir / "country.json"
        if not country_config_path.exists():
            errors.append(f"{country_config_path}: missing country configuration")
            continue
        country_config = _load_model(country_config_path, CountryConfig)
        if country_config.country_code != country_code.upper():
            errors.append(
                f"{country_config_path}: country_code {country_config.country_code} does not match config"
            )
        country = CountryData(config=country_config)

        source_rows = _load_ndjson(country_dir / "sources" / "sources.ndjson", SourceDocument, errors)
        sources_by_issue: dict[str, SourceDocument] = {}
        for source in source_rows:
            if source.issue_id in sources_by_issue:
                errors.append(f"{country_dir}: duplicate source registry entry for {source.issue_id}")
            sources_by_issue[source.issue_id] = source
            if not preview and source.demo:
                errors.append(f"{country_dir}: demonstration source present in production data: {source.issue_id}")
            if not preview and source.sha256 is None:
                errors.append(f"{source.issue_id}: production sources require a sha256 checksum")

        issue_dirs = sorted(path.parent for path in (country_dir).glob("[0-9][0-9][0-9][0-9]/*/issue.json"))
        for issue_dir in issue_dirs:
            issue = _load_model(issue_dir / "issue.json", GazetteIssue)
            if issue.issue_id in seen_issue_ids:
                errors.append(f"{issue_dir}: duplicate issue_id {issue.issue_id}")
                continue
            seen_issue_ids.add(issue.issue_id)
            if issue.country != country_config.country_code:
                errors.append(f"{issue_dir}: issue country {issue.country} does not match {country_config.country_code}")
            pages = _load_ndjson(issue_dir / "pages.ndjson", GazettePage, errors)
            texts = _read_texts(issue_dir / "text.jsonl.gz")
            if len(pages) != len(texts):
                errors.append(f"{issue_dir}: page/text count mismatch ({len(pages)} vs {len(texts)})")
            for page in pages:
                if page.uid in seen_page_uids:
                    errors.append(f"{issue_dir}: duplicate page uid {page.uid}")
                seen_page_uids.add(page.uid)
                if page.issue_id != issue.issue_id:
                    errors.append(f"{issue_dir}: page {page.uid} belongs to {page.issue_id}")
                if page.uid not in texts:
                    errors.append(f"{issue_dir}: missing text for page {page.uid}")
                if page.physical_pdf_page > issue.page_count:
                    errors.append(f"{issue_dir}: page {page.uid} exceeds issue page_count")
            source = sources_by_issue.get(issue.issue_id)
            if source is None:
                errors.append(f"{issue_dir}: no source registry entry for {issue.issue_id}")
                source = SourceDocument(
                    source_file=issue.source_file,
                    issue_id=issue.issue_id,
                    sha256="0" * 64 if not preview else None,
                    bytes=None,
                    official_url=issue.source_url,
                    checked_at=issue.publication_date,
                    demo=preview,
                )
            if source.source_file != issue.source_file:
                errors.append(
                    f"{issue_dir}: source registry file {source.source_file} != issue source_file {issue.source_file}"
                )
            if source.official_url and issue.source_url and str(source.official_url) != str(issue.source_url):
                errors.append(f"{issue_dir}: source registry and issue official URLs disagree")
            if not preview and raw_root is not None:
                source_path = raw_root / issue.source_file
                if source_path.exists():
                    actual_sha = _sha256(source_path)
                    if source.sha256 != actual_sha:
                        errors.append(f"{source_path}: sha256 does not match source registry")
                    if source.bytes is not None and source.bytes != source_path.stat().st_size:
                        errors.append(f"{source_path}: byte size does not match source registry")
                else:
                    warnings.append(f"{issue.source_file}: local extraction input not present; registry checksum kept")
            country.issues.append(
                IssueBundle(
                    issue=issue,
                    country=country_config,
                    pages=tuple(sorted(pages, key=lambda page: page.physical_pdf_page)),
                    texts=texts,
                    source=source,
                )
            )

        country.people = _load_ndjson(country_dir / "entities" / "people.ndjson", PersonEntity, errors)
        country.organisations = _load_ndjson(
            country_dir / "entities" / "organisations.ndjson", OrganisationEntity, errors
        )
        country.variants = _load_ndjson(
            country_dir / "entities" / "name-variants.ndjson", NameVariant, errors
        )
        country.documents = _load_ndjson(
            country_dir / "sources" / "documents.ndjson", SourceDocumentSnapshot, errors
        )
        country.sources = _load_ndjson(
            country_dir / "sources" / "registry.ndjson", SourceRegistryEntry, errors
        )
        country.records = _load_ndjson(country_dir / "records" / "records.ndjson", CuratedRecord, errors)

        documents_by_id = {document.document_id: document for document in country.documents}
        if len(documents_by_id) != len(country.documents):
            errors.append(f"{country_dir}: duplicate document_id in source documents")
        for document in country.documents:
            if document.country_code != country_config.country_code:
                errors.append(f"{country_dir}: document {document.document_id} country mismatch")
        for registry_entry in country.sources:
            if registry_entry.country_code != country_config.country_code:
                errors.append(f"{country_dir}: source {registry_entry.source_id} country mismatch")
        seen_source_ids: set[str] = set()
        for registry_entry in country.sources:
            if registry_entry.source_id in seen_source_ids:
                errors.append(f"{country_dir}: duplicate source_id {registry_entry.source_id}")
            seen_source_ids.add(registry_entry.source_id)

        for person in country.people:
            if person.person_id in seen_person_ids:
                errors.append(f"{country_dir}: duplicate person_id {person.person_id}")
            seen_person_ids.add(person.person_id)
            if person.country_code != country_config.country_code:
                errors.append(f"{country_dir}: person {person.person_id} country mismatch")
        for org in country.organisations:
            if org.organisation_id in seen_org_ids:
                errors.append(f"{country_dir}: duplicate organisation_id {org.organisation_id}")
            seen_org_ids.add(org.organisation_id)
            if org.country_code != country_config.country_code:
                errors.append(f"{country_dir}: organisation {org.organisation_id} country mismatch")

        people_by_id = {person.person_id: person for person in country.people}
        orgs_by_id = {org.organisation_id: org for org in country.organisations}
        issues_by_id = {issue.issue.issue_id: issue for issue in country.issues}

        for variant in country.variants:
            if variant.person_id not in people_by_id:
                errors.append(f"{country_dir}: name variant {variant.variant_id} references unknown person")
            for uid in variant.source_record_uids:
                if uid not in {record.uid for record in country.records}:
                    errors.append(f"{country_dir}: name variant {variant.variant_id} references unknown record {uid}")

        for record in country.records:
            if record.uid in seen_record_uids:
                errors.append(f"{country_dir}: duplicate record uid {record.uid}")
                continue
            seen_record_uids.add(record.uid)
            category = RECORD_TYPE_CATEGORY[record.record_type]
            excerpt = normalise_text(record.source.excerpt)
            if record.source.kind == "pdf":
                issue = issues_by_id.get(record.issue_id)
                if issue is None:
                    errors.append(f"{record.uid}: unknown issue_id {record.issue_id}")
                    continue
                expected_prefix = f"{record.issue_id}-{category}-"
                if not record.uid.startswith(expected_prefix):
                    errors.append(f"{record.uid}: UID must start with {expected_prefix}")
                try:
                    source_page = issue.page(record.source.pdf_page)
                except KeyError as exc:
                    errors.append(f"{record.uid}: {exc}")
                    continue
                if record.source.printed_page is not None and source_page.printed_page != record.source.printed_page:
                    errors.append(
                        f"{record.uid}: printed page {record.source.printed_page} does not match extracted page "
                        f"{source_page.printed_page}"
                    )
                if excerpt not in normalise_text(issue.texts[source_page.uid]):
                    errors.append(f"{record.uid}: source excerpt not found on extracted page {source_page.uid}")
            else:
                document = documents_by_id.get(record.source.document_id or "")
                if document is None:
                    errors.append(f"{record.uid}: unknown source document {record.source.document_id}")
                    continue
                expected_uid = f"{country_config.country_code}-{document.publication_date.year if document.publication_date else (record.publication_date.year if record.publication_date else 0)}"
                if not record.uid.startswith(expected_uid + "-") and not record.uid.startswith(f"{country_config.country_code}-"):
                    errors.append(f"{record.uid}: UID must start with {country_config.country_code}-<YEAR>-")
                if excerpt not in normalise_text(document.text):
                    errors.append(f"{record.uid}: source excerpt not found in document {document.document_id}")
                if record.source.sha256 and record.source.sha256 != document.source_sha256:
                    errors.append(f"{record.uid}: source sha256 does not match document {document.document_id}")
                if record.source.official_url and str(record.source.official_url) != str(document.official_url):
                    errors.append(f"{record.uid}: source URL does not match document {document.document_id}")
                if record.publication_date is None:
                    errors.append(f"{record.uid}: non-PDF records require publication_date")
                for registry_entry in country.sources:
                    if registry_entry.source_id == document.source_id:
                        break
                else:
                    errors.append(f"{record.uid}: document source {document.source_id} missing from registry")
            for person_ref in record.people:
                _validate_person_reference(
                    record, person_ref, people_by_id, orgs_by_id, country_config, errors
                )
            for org_id in record.organisation_ids:
                org = orgs_by_id.get(org_id)
                if org is None:
                    errors.append(f"{record.uid}: unknown organisation {org_id}")
                elif org.country_code != country_config.country_code:
                    errors.append(f"{record.uid}: organisation {org_id} country mismatch")
            if record.tender is not None and record.tender.issuer_organisation_id:
                issuer = orgs_by_id.get(record.tender.issuer_organisation_id)
                if issuer is None:
                    errors.append(
                        f"{record.uid}: unknown tender issuer {record.tender.issuer_organisation_id}"
                    )
                elif issuer.country_code != country_config.country_code:
                    errors.append(f"{record.uid}: tender issuer country mismatch")
        countries.append(country)

    if not preview:
        demo_files = list((data_root).glob("**/demo-gazette.pdf"))
        if demo_files:
            errors.append(f"demonstration source file present in production data: {demo_files[0]}")
        for country in countries:
            for issue in country.issues:
                if issue.issue.parser_version.startswith("demo"):
                    errors.append(f"{issue.issue.issue_id}: demo issue present in production data")
                if issue.source.demo:
                    errors.append(f"{issue.issue.issue_id}: demo source present in production data")

    if errors:
        raise ContentValidationError(errors)

    site = SiteData(
        config=config,
        site_url=site_url,
        preview=preview,
        countries=countries,
        warnings=warnings,
    )
    if not site.issues:
        warnings.append("No Gazette issues are available.")
    return site


def _validate_person_reference(
    record: CuratedRecord,
    person_ref: PersonReference,
    people_by_id: dict[str, PersonEntity],
    orgs_by_id: dict[str, OrganisationEntity],
    country_config: CountryConfig,
    errors: list[str],
) -> None:
    person = people_by_id.get(person_ref.person_id)
    if person is None:
        errors.append(f"{record.uid}: unknown person {person_ref.person_id}")
        return
    if person.country_code != country_config.country_code:
        errors.append(f"{record.uid}: person {person_ref.person_id} country mismatch")
    for org_id in person_ref.organisation_ids:
        org = orgs_by_id.get(org_id)
        if org is None:
            errors.append(f"{record.uid}: unknown organisation {org_id}")
        elif org.country_code != country_config.country_code:
            errors.append(f"{record.uid}: organisation {org_id} country mismatch")


def iter_all_pages(site: SiteData) -> Iterable[tuple[IssueBundle, GazettePage]]:
    for issue in site.issues:
        for page in issue.pages:
            yield issue, page
