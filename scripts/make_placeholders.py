"""Generate architectural blueprint placeholder SVGs for UI layout slots."""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src" / "assets" / "img" / "placeholders"

PLACEHOLDERS: list[tuple[str, int, int, str, str]] = [
    ("hero-platform-ui", 1200, 920, "Hero product UI or editorial visual", "dark"),
    ("workflow-ingest", 800, 520, "Multi-country gazette PDFs & portals", "light"),
    ("workflow-extract", 800, 520, "Cross-publisher structured indexing", "light"),
    ("workflow-verify", 800, 520, "Closing deadlines & page provenance", "light"),
    ("bento-tenders-feature", 880, 520, "Procurement & tender discovery visual", "light"),
    ("bento-gazettes-feature", 880, 520, "Page-level gazette archive visual", "light"),
    ("coverage-map-visual", 1200, 680, "Global jurisdiction coverage map", "dark"),
    ("provenance-audit-preview", 960, 720, "Annotated gazette page & SHA-256 check", "light"),
    ("section-tenders", 760, 480, "Tenders section header visual", "light"),
    ("section-gazettes", 760, 480, "Gazettes archive header visual", "light"),
    ("section-people", 760, 480, "Verified people directory visual", "light"),
    ("section-organisations", 760, 480, "Organisations directory visual", "light"),
    ("section-notices", 760, 480, "Public notices header visual", "light"),
    ("section-regulations", 760, 480, "Regulations & acts header visual", "light"),
    ("section-countries", 760, 480, "Country coverage header visual", "light"),
    ("section-sources", 760, 480, "Official source registry visual", "light"),
    ("section-about", 760, 480, "Methodology & index overview visual", "light"),
    ("section-corrections", 760, 480, "Corrections & verification visual", "light"),
]

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#f1f5f9",
        "grid": "#cbd5e1",
        "grid_opacity": "0.55",
        "border": "#cbd5e1",
        "inset": "#94a3b8",
        "bracket": "#2563eb",
        "card_bg": "#ffffff",
        "card_stroke": "#cbd5e1",
        "pill_bg": "#eff6ff",
        "pill_stroke": "#bfdbfe",
        "pill_text": "#2563eb",
        "filename": "#0f172a",
        "meta": "#475569",
        "path": "#64748b",
    },
    "dark": {
        "bg": "#0b1f38",
        "grid": "#1e3a5f",
        "grid_opacity": "0.65",
        "border": "#1e3a5f",
        "inset": "#335c8d",
        "bracket": "#f0801a",
        "card_bg": "#0f2947",
        "card_stroke": "#264b78",
        "pill_bg": "#15365d",
        "pill_stroke": "#2c5b92",
        "pill_text": "#60a5fa",
        "filename": "#ffffff",
        "meta": "#cbd5e1",
        "path": "#94a3b8",
    },
}


def render_svg(name: str, width: int, height: int, purpose: str, theme: str) -> str:
    """Return an architectural blueprint placeholder SVG with filename and dimensions."""
    palette = THEMES[theme]
    filename = f"{name}.svg"
    cx = width / 2
    cy = height / 2

    inset = 16
    x2 = width - inset
    y2 = height - inset
    arm = 14

    card_w = min(width - 64, max(500, int(width * 0.76)))
    card_h = min(height - 76, 224)
    card_x = cx - card_w / 2
    card_y = cy - card_h / 2

    pill_w = 160
    pill_h = 26
    pill_x = cx - pill_w / 2
    pill_y = card_y + 24

    file_size = 27 if width < 1000 else 28
    meta_size = 16 if width < 1000 else 16.5

    pattern_id = f"grid-{name}"
    safe_file = html.escape(filename)
    safe_meta = html.escape(f"{width} × {height} px — {purpose}")
    safe_path = html.escape(f"src/assets/img/placeholders/{filename}")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Placeholder: {safe_file}">
  <defs>
    <pattern id="{pattern_id}" width="32" height="32" patternUnits="userSpaceOnUse">
      <path d="M 32 0 L 0 0 0 32" fill="none" stroke="{palette['grid']}" stroke-width="1" opacity="{palette['grid_opacity']}"/>
    </pattern>
  </defs>

  <rect width="{width}" height="{height}" fill="{palette['bg']}"/>
  <rect width="{width}" height="{height}" fill="url(#{pattern_id})"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" fill="none" stroke="{palette['border']}" stroke-width="1"/>

  <rect x="{inset}" y="{inset}" width="{width - inset * 2}" height="{height - inset * 2}" fill="none" stroke="{palette['inset']}" stroke-width="1" stroke-dasharray="5 5"/>

  <g fill="none" stroke="{palette['bracket']}" stroke-width="2" stroke-linecap="square">
    <path d="M {inset} {inset + arm} V {inset} H {inset + arm}"/>
    <path d="M {x2 - arm} {inset} H {x2} V {inset + arm}"/>
    <path d="M {inset} {y2 - arm} V {y2} H {inset + arm}"/>
    <path d="M {x2 - arm} {y2} H {x2} V {y2 - arm}"/>
  </g>

  <rect x="{card_x:.1f}" y="{card_y:.1f}" width="{card_w:.1f}" height="{card_h:.1f}" rx="12" fill="{palette['card_bg']}" stroke="{palette['card_stroke']}" stroke-width="1"/>

  <rect x="{pill_x:.1f}" y="{pill_y:.1f}" width="{pill_w}" height="{pill_h}" rx="999" fill="{palette['pill_bg']}" stroke="{palette['pill_stroke']}" stroke-width="1"/>
  <text x="{cx:.1f}" y="{pill_y + 17:.1f}" font-family="Inter, system-ui, -apple-system, sans-serif" font-size="11.5" font-weight="700" letter-spacing="1.3" text-anchor="middle" fill="{palette['pill_text']}">PLACEHOLDER ASSET</text>

  <text x="{cx:.1f}" y="{card_y + 102:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="{file_size}" font-weight="700" text-anchor="middle" fill="{palette['filename']}">{safe_file}</text>
  <text x="{cx:.1f}" y="{card_y + 140:.1f}" font-family="Inter, system-ui, -apple-system, sans-serif" font-size="{meta_size}" font-weight="500" text-anchor="middle" fill="{palette['meta']}">{safe_meta}</text>
  <text x="{cx:.1f}" y="{card_y + 178:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="12.5" font-weight="500" text-anchor="middle" fill="{palette['path']}">{safe_path}</text>
</svg>
"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, width, height, purpose, theme in PLACEHOLDERS:
        path = OUT_DIR / f"{name}.svg"
        path.write_text(render_svg(name, width, height, purpose, theme), encoding="utf-8")
    print(f"Wrote {len(PLACEHOLDERS)} blueprint placeholder SVGs to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
