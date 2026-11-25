"""Generate deterministic newsprint-style placeholder SVGs for editorial slots."""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "src" / "assets" / "img" / "placeholders"

PLACEHOLDERS: list[tuple[str, int, int, str]] = [
    ("home-lead", 1600, 760, "Lead photograph: gazette pages / public office"),
    ("home-feature-tenders", 800, 560, "Feature photo: procurement / tenders"),
    ("home-feature-records", 800, 560, "Feature photo: archive / records"),
    ("home-provenance", 900, 1100, "Portrait photo: annotated gazette page"),
    ("banner-tenders", 1600, 360, "Section photo"),
    ("banner-gazettes", 1600, 360, "Section photo"),
    ("banner-people", 1600, 360, "Section photo"),
    ("banner-organisations", 1600, 360, "Section photo"),
    ("banner-notices", 1600, 360, "Section photo"),
    ("banner-regulations", 1600, 360, "Section photo"),
    ("banner-countries", 1600, 360, "Section photo"),
    ("banner-sources", 1600, 360, "Section photo"),
    ("banner-about", 1600, 360, "Section photo"),
    ("banner-corrections", 1600, 360, "Section photo"),
]


def render_svg(name: str, width: int, height: int, purpose: str) -> str:
    """Return a clean newsprint wireframe placeholder SVG with centred label metadata."""
    filename = f"{name}.svg"
    cx = width / 2
    cy = height / 2

    box_w = min(width - 40, max(320, int(width * 0.56)))
    box_h = min(height - 36, max(108, int(height * 0.36)))
    if box_h > 176:
        box_h = 176
    if box_w > 660:
        box_w = 660

    box_x = cx - box_w / 2
    box_y = cy - box_h / 2

    scale = min(box_w / 360.0, box_h / 120.0, 1.45)
    title_size = round(max(15, 20 * scale), 1)
    dim_size = round(max(12, 14 * scale), 1)
    purpose_size = round(max(11, 13 * scale), 1)

    y_title = cy - box_h * 0.17
    y_dim = cy + box_h * 0.07
    y_purpose = cy + box_h * 0.28

    safe_file = html.escape(filename)
    safe_dims = html.escape(f"{width} × {height}")
    safe_purpose = html.escape(purpose)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Placeholder: {safe_file}">
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" fill="#e6dfd0" stroke="#b8ab94" stroke-width="2"/>
  <line x1="2" y1="2" x2="{width - 2}" y2="{height - 2}" stroke="#d3c9b6" stroke-width="1.5"/>
  <line x1="{width - 2}" y1="2" x2="2" y2="{height - 2}" stroke="#d3c9b6" stroke-width="1.5"/>
  <rect x="{box_x:.1f}" y="{box_y:.1f}" width="{box_w:.1f}" height="{box_h:.1f}" rx="0" fill="#fbf8f2" stroke="#b8ab94" stroke-width="1.5"/>
  <g text-anchor="middle">
    <text x="{cx:.1f}" y="{y_title:.1f}" font-family="Georgia, 'Times New Roman', serif" font-size="{title_size}" font-weight="700" fill="#161412">{safe_file}</text>
    <text x="{cx:.1f}" y="{y_dim:.1f}" font-family="Inter, Arial, sans-serif" font-size="{dim_size}" font-weight="600" fill="#2f2a25">{safe_dims}</text>
    <text x="{cx:.1f}" y="{y_purpose:.1f}" font-family="Inter, Arial, sans-serif" font-size="{purpose_size}" font-weight="500" fill="#6b645a">{safe_purpose}</text>
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
