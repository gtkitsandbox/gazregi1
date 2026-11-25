"""Generate deterministic wireframe placeholder SVGs for UI layout slots."""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src" / "assets" / "img" / "placeholders"

PLACEHOLDERS: list[tuple[str, int, int, str]] = [
    ("home-hero", 1200, 960, "Hero visual: product UI or illustration"),
    ("home-hero-float-1", 480, 300, "Floating card: tender preview"),
    ("home-hero-float-2", 420, 260, "Floating card: gazette page snippet"),
    ("home-search-demo", 1400, 860, "Screenshot: search results UI"),
    ("problem-pdf", 640, 420, "Published once, inside a PDF"),
    ("problem-reference", 640, 420, "The reference you would never guess"),
    ("problem-deadline", 640, 420, "A deadline does not wait"),
    ("how-1-search", 800, 600, "Step 1: search"),
    ("how-2-verify", 800, 600, "Step 2: verify source page"),
    ("how-3-act", 800, 600, "Step 3: act before deadline"),
    ("browse-tenders", 640, 400, "Category thumbnail"),
    ("browse-gazettes", 640, 400, "Category thumbnail"),
    ("browse-people", 640, 400, "Category thumbnail"),
    ("browse-organisations", 640, 400, "Category thumbnail"),
    ("browse-notices", 640, 400, "Category thumbnail"),
    ("browse-regulations", 640, 400, "Category thumbnail"),
    ("coverage-world-map", 1600, 760, "World coverage map"),
    ("provenance-document", 960, 760, "Annotated gazette page with provenance callouts"),
    ("cta-band", 1600, 520, "CTA background image"),
    ("banner-tenders", 1600, 440, "Section banner"),
    ("banner-gazettes", 1600, 440, "Section banner"),
    ("banner-people", 1600, 440, "Section banner"),
    ("banner-organisations", 1600, 440, "Section banner"),
    ("banner-notices", 1600, 440, "Section banner"),
    ("banner-regulations", 1600, 440, "Section banner"),
    ("banner-countries", 1600, 440, "Section banner"),
    ("banner-sources", 1600, 440, "Section banner"),
    ("banner-about", 1600, 440, "Section banner"),
    ("banner-corrections", 1600, 440, "Section banner"),
]


def render_svg(name: str, width: int, height: int, purpose: str) -> str:
    """Return a clean wireframe placeholder SVG with centred label metadata."""
    filename = f"{name}.svg"
    cx = width / 2
    cy = height / 2

    # Scale label box and font sizes proportionally while staying readable.
    box_w = min(width - 40, max(300, int(width * 0.56)))
    box_h = min(height - 36, max(108, int(height * 0.34)))
    if box_h > 176:
        box_h = 176
    if box_w > 640:
        box_w = 640

    box_x = cx - box_w / 2
    box_y = cy - box_h / 2

    scale = min(box_w / 360.0, box_h / 120.0, 1.45)
    title_size = round(max(15, 20 * scale), 1)
    dim_size = round(max(12, 14 * scale), 1)
    purpose_size = round(max(11, 13 * scale), 1)

    y_title = cy - box_h * 0.17
    y_dim = cy + box_h * 0.06
    y_purpose = cy + box_h * 0.27

    safe_file = html.escape(filename)
    safe_dims = html.escape(f"{width} × {height}")
    safe_purpose = html.escape(purpose)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Placeholder: {safe_file}">
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" fill="#e9edf2" stroke="#c3ccd7" stroke-width="2"/>
  <line x1="2" y1="2" x2="{width - 2}" y2="{height - 2}" stroke="#d3dae3" stroke-width="1.5"/>
  <line x1="{width - 2}" y1="2" x2="2" y2="{height - 2}" stroke="#d3dae3" stroke-width="1.5"/>
  <rect x="{box_x:.1f}" y="{box_y:.1f}" width="{box_w:.1f}" height="{box_h:.1f}" rx="12" fill="#ffffff" stroke="#c3ccd7" stroke-width="1.5"/>
  <g font-family="Inter, Arial, sans-serif" text-anchor="middle">
    <text x="{cx:.1f}" y="{y_title:.1f}" font-size="{title_size}" font-weight="700" fill="#0b2440">{safe_file}</text>
    <text x="{cx:.1f}" y="{y_dim:.1f}" font-size="{dim_size}" font-weight="600" fill="#3b526b">{safe_dims}</text>
    <text x="{cx:.1f}" y="{y_purpose:.1f}" font-size="{purpose_size}" font-weight="500" fill="#5b6d82">{safe_purpose}</text>
  </g>
</svg>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, width, height, purpose in PLACEHOLDERS:
        path = OUT_DIR / f"{name}.svg"
        path.write_text(render_svg(name, width, height, purpose), encoding="utf-8")
    print(f"Wrote {len(PLACEHOLDERS)} placeholder SVGs to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
