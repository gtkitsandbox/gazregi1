"""Validated content models for the GazetteRegistry static platform.

Extraction output and operator-curated records live in separate schemas.  Raw
PDFs are extraction inputs only; nothing here depends on a database or a
runtime Worker.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PositiveInt, model_validator

COUNTRY_CODE_RE = r"^[A-Z]{2}$"
ISSUE_ID_RE = r"^[A-Z]{2}-\d{4}-\d+$"
RECORD_UID_RE = r"^[A-Z]{2}-\d{4}-\d+-(?:APPT|TEND|NOTC|REGL)-\d{3,}$"
PERSON_ID_RE = r"^person:[a-z]{2}:[a-z0-9]+(?:-[a-z0-9]+)*$"
ORG_ID_RE = r"^org:[a-z]{2}:[a-z0-9]+(?:-[a-z0-9]+)*$"
SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

RecordType = Literal[
    "appointment",
    "commissioning",
    "promotion",
    "professional_position",
    "organisational_appointment",
    "tender",
    "public_notice",
    "regulation",
]
PositionKind = Literal[
    "appointment",
    "commissioning",
    "promotion",
    "professional",
    "organisational",
    "acting",
    "other",
]
VerificationStatus = Literal["operator_verified", "unverified"]
TenderSector = Literal[
    "civil_works",
    "goods",
    "consultancy",
    "services",
    "it",
    "maintenance",
    "auction",
    "other",
]
NoticeCategory = Literal[
    "land",
    "insolvency",
    "estate",
    "court",
    "licensing",
    "professional",
    "other",
]
InstrumentType = Literal[
    "act",
    "regulation",
    "order",
    "rule",
    "notification",
    "by_law",
    "other",
]
OrganisationType = Literal[
    "government_body",
    "company",
    "professional_body",
    "statutory_body",
    "other",
]

RECORD_TYPE_CATEGORY: dict[str, str] = {
    "appointment": "APPT",
    "commissioning": "APPT",
    "promotion": "APPT",
    "professional_position": "APPT",
    "organisational_appointment": "APPT",
    "tender": "TEND",
    "public_notice": "NOTC",
    "regulation": "REGL",
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SiteConfig(FrozenModel):
    site_name: str = Field(min_length=1)
    default_site_url: str = Field(min_length=1)
    countries: list[str]
    corrections_email: str | None = None
    corrections_note: str | None = None


class CountryConfig(FrozenModel):
    country_code: str = Field(pattern=COUNTRY_CODE_RE)
    name: str = Field(min_length=1)
    languages: list[str] = Field(min_length=1)
    gazette_name: str = Field(min_length=1)
    publisher_name: str | None = None
    default_language: str = Field(min_length=2)


class SourceRecord(FrozenModel):
    url: HttpUrl | None
    gazette_no: str
    page_start: int | None
    page_end: int | None
    language: str | None


class GazettePage(FrozenModel):
    uid: str
    issue_id: str
    physical_pdf_page: PositiveInt
    printed_page: PositiveInt | None
    section: str | None
    category: str
    subcategory: str | None
    title: str
    summary: str | None
    keywords: list[str]
    source: SourceRecord


class GazetteIssue(FrozenModel):
    issue_id: str = Field(pattern=ISSUE_ID_RE)
    country: str = Field(pattern=COUNTRY_CODE_RE)
    gazette_no: str
    gazette_type: str
    edition: str
    publication_date: date
    source_url: HttpUrl | None
    source_file: str
    page_count: PositiveInt
    parser_version: str
    extraction_method: str
    extracted_at: str


class SourceDocument(FrozenModel):
    """Checksum/provenance for a local extraction input.

    `sha256` may be null only for isolated demonstration data.  Production
    builds reject demonstration documents.
    """

    source_file: str = Field(min_length=1)
    issue_id: str = Field(pattern=ISSUE_ID_RE)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    bytes: int | None = Field(default=None, ge=0)
    official_url: HttpUrl | None = None
    checked_at: date
    demo: bool = False


class PersonReference(FrozenModel):
    person_id: str = Field(pattern=PERSON_ID_RE)
    published_name: str = Field(min_length=1)
    position: str | None = None
    position_kind: PositionKind | None = None
    organisation_ids: list[str] = Field(default_factory=list)


class TenderDetail(FrozenModel):
    reference: str = Field(min_length=1)
    issuer_organisation_id: str | None = Field(default=None, pattern=ORG_ID_RE)
    sector: TenderSector
    location: str | None = None
    closing_date: date | None = None
    closing_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    document_deadline: date | None = None
    bid_security_lkr: int | None = Field(default=None, ge=0)


class RegulationDetail(FrozenModel):
    instrument_type: InstrumentType
    instrument_number: str | None = None
    effective_date: date | None = None


class NoticeDetail(FrozenModel):
    category: NoticeCategory


class RecordSource(FrozenModel):
    pdf_page: PositiveInt
    printed_page: PositiveInt | None = None
    excerpt: str = Field(min_length=20)
    official_url: HttpUrl | None = None


class CuratedRecord(FrozenModel):
    uid: str = Field(pattern=RECORD_UID_RE)
    record_type: RecordType
    title: str = Field(min_length=1)
    summary: str | None = None
    issue_id: str = Field(pattern=ISSUE_ID_RE)
    people: list[PersonReference] = Field(default_factory=list)
    organisation_ids: list[str] = Field(default_factory=list)
    location: str | None = None
    keywords: list[str] = Field(default_factory=list)
    tender: TenderDetail | None = None
    regulation: RegulationDetail | None = None
    notice: NoticeDetail | None = None
    source: RecordSource

    @model_validator(mode="after")
    def _type_specific_fields(self) -> "CuratedRecord":
        if self.record_type == "tender" and self.tender is None:
            raise ValueError("tender records require a tender object")
        if self.record_type == "regulation" and self.regulation is None:
            raise ValueError("regulation records require a regulation object")
        if self.record_type == "public_notice" and self.notice is None:
            raise ValueError("public_notice records require a notice object")
        if self.record_type != "tender" and self.tender is not None:
            raise ValueError("tender object is only valid on tender records")
        if self.record_type != "regulation" and self.regulation is not None:
            raise ValueError("regulation object is only valid on regulation records")
        if self.record_type != "public_notice" and self.notice is not None:
            raise ValueError("notice object is only valid on public_notice records")
        if self.record_type in {
            "appointment",
            "commissioning",
            "promotion",
            "professional_position",
            "organisational_appointment",
        }:
            if not self.people:
                raise ValueError(f"{self.record_type} records require at least one person")
            for person in self.people:
                if not person.position:
                    raise ValueError(f"{self.record_type} person entries require a position")
                if not person.organisation_ids:
                    raise ValueError(
                        f"{self.record_type} person entries require an organisation"
                    )
        return self


class PersonEntity(FrozenModel):
    person_id: str = Field(pattern=PERSON_ID_RE)
    country_code: str = Field(pattern=COUNTRY_CODE_RE)
    canonical_name: str = Field(min_length=1)
    identity_status: VerificationStatus
    verified_at: date | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def _verification(self) -> "PersonEntity":
        if self.identity_status == "operator_verified" and self.verified_at is None:
            raise ValueError("operator_verified people require verified_at")
        if self.person_id.split(":")[1].upper() != self.country_code:
            raise ValueError("person_id country prefix must match country_code")
        return self


class OrganisationEntity(FrozenModel):
    organisation_id: str = Field(pattern=ORG_ID_RE)
    country_code: str = Field(pattern=COUNTRY_CODE_RE)
    name: str = Field(min_length=1)
    type: OrganisationType
    aliases: list[str] = Field(default_factory=list)
    identity_status: VerificationStatus = "unverified"
    verified_at: date | None = None
    basis: str | None = None

    @model_validator(mode="after")
    def _country(self) -> "OrganisationEntity":
        if self.organisation_id.split(":")[1].upper() != self.country_code:
            raise ValueError("organisation_id country prefix must match country_code")
        if self.identity_status == "operator_verified" and self.verified_at is None:
            raise ValueError("operator_verified organisations require verified_at")
        return self


class NameVariant(FrozenModel):
    variant_id: str = Field(min_length=1)
    person_id: str = Field(pattern=PERSON_ID_RE)
    name: str = Field(min_length=1)
    verification: VerificationStatus
    basis: str | None = None
    reviewed_at: date | None = None
    source_record_uids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _verification(self) -> "NameVariant":
        if self.verification == "operator_verified" and (
            self.reviewed_at is None or not self.basis
        ):
            raise ValueError(
                "operator_verified name variants require reviewed_at and basis"
            )
        return self


def normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalise_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def slugify_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
