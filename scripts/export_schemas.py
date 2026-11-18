"""Export JSON Schema files from the validated Python content models."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pydantic import BaseModel  # noqa: E402

from content.models import (  # noqa: E402
    CountryConfig,
    CuratedRecord,
    GazetteIssue,
    GazettePage,
    NameVariant,
    OrganisationEntity,
    PersonEntity,
    SiteConfig,
    SourceDocument,
    SourceDocumentSnapshot,
    SourceRegistryEntry,
)

MODELS: dict[str, type[BaseModel]] = {
    "site": SiteConfig,
    "country": CountryConfig,
    "issue": GazetteIssue,
    "page-record": GazettePage,
    "source": SourceDocument,
    "source-document": SourceDocumentSnapshot,
    "source-registry": SourceRegistryEntry,
    "record": CuratedRecord,
    "person": PersonEntity,
    "organisation": OrganisationEntity,
    "name-variant": NameVariant,
}


def main() -> int:
    output = ROOT / "schemas"
    output.mkdir(exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://gazetteregistry.com/schemas/{name}.schema.json",
            **schema,
        }
        path = output / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
