"""Generate compressed JPGs from AI studio renders and dark-obsidian coverage cartography."""

from __future__ import annotations

from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "src" / "assets" / "img"

AI_SOURCES: dict[str, tuple[Path, int]] = {
    "hero-main.jpg": (
        Path("/home/codespace/.gemini/antigravity-cli/brain/686d59a0-522d-4afc-952d-3cf044198402/crystalline_index_prism_hero_1795615509688.jpg"),
        1280,
    ),
    "provenance-verify.jpg": (
        Path("/home/codespace/.gemini/antigravity-cli/brain/686d59a0-522d-4afc-952d-3cf044198402/optical_lens_archival_paper_v2_1795615552583.jpg"),
        1200,
    ),
}

# Simplified landmass polygons in (lon, lat) for dot-matrix cartography.
CONTINENTS: list[list[tuple[float, float]]] = [
    # North America
    [(-168, 65), (-140, 70), (-110, 70), (-82, 63), (-62, 52), (-54, 47), (-70, 41), (-81, 30), (-82, 24), (-90, 21), (-97, 25), (-105, 20), (-84, 10), (-78, 8), (-88, 14), (-105, 19), (-115, 30), (-125, 42), (-132, 55), (-160, 58)],
    # Greenland
    [(-55, 60), (-42, 60), (-22, 70), (-18, 81), (-50, 82), (-68, 76)],
    # South America
    [(-79, 9), (-62, 10), (-50, 1), (-35, -6), (-39, -18), (-48, -28), (-58, -38), (-67, -54), (-74, -52), (-73, -38), (-71, -18), (-81, -5)],
    # Europe
    [(-10, 36), (-9, 43), (-2, 43), (-5, 48), (2, 51), (8, 55), (5, 61), (18, 69), (30, 70), (42, 67), (58, 68), (58, 50), (42, 43), (29, 41), (22, 37), (14, 38), (10, 44), (3, 42), (-5, 36)],
    # UK / Ireland
    [(-10, 51), (-5, 55), (-6, 58), (0, 58), (2, 52), (-5, 50)],
    # Africa
    [(-17, 15), (-13, 28), (-5, 36), (11, 37), (25, 32), (33, 31), (43, 12), (51, 12), (41, -2), (40, -15), (34, -26), (20, -35), (15, -24), (12, -6), (8, 4), (-7, 4), (-16, 11)],
    # Madagascar
    [(44, -25), (47, -25), (50, -13), (47, -15)],
    # Asia
    [(28, 41), (40, 43), (50, 40), (58, 50), (62, 68), (95, 75), (135, 71), (170, 66), (160, 56), (141, 52), (130, 42), (122, 38), (121, 24), (108, 20), (104, 2), (100, 12), (96, 16), (88, 22), (80, 8), (72, 20), (66, 25), (56, 26), (50, 29), (58, 22), (52, 16), (44, 13), (35, 29)],
    # Japan
    [(130, 31), (136, 34), (141, 38), (145, 44), (140, 45), (137, 37), (131, 34)],
    # Indonesia / Philippines arc
    [(96, 5), (106, -6), (118, -8), (118, 4), (108, 1)],
    [(120, 12), (126, 8), (123, 18), (120, 18)],
    # Australia
    [(114, -22), (128, -14), (136, -12), (142, -11), (153, -26), (150, -37), (138, -36), (129, -32), (115, -34)],
    # New Zealand
    [(167, -46), (174, -41), (178, -37), (173, -35), (171, -43)],
]

# Active GazetteRegistry jurisdictions (lon, lat, color_hex)
ACTIVE_HUBS: list[tuple[float, float, str]] = [
    (-0.1, 51.5, "#f5f5f4"),   # UK
    (-6.3, 53.3, "#f5f5f4"),   # IE
    (4.9, 52.4, "#f5f5f4"),    # NL
    (13.4, 52.5, "#f5f5f4"),   # DE
    (-77.0, 38.9, "#34d399"),  # US
    (-75.7, 45.4, "#f5f5f4"),  # CA
    (36.8, -1.3, "#f59e0b"),   # KE
    (28.2, -25.7, "#f59e0b"),  # ZA
    (79.9, 6.9, "#f59e0b"),    # LK
    (73.5, 4.2, "#34d399"),    # MV
    (90.4, 23.8, "#f59e0b"),   # BD
    (103.8, 1.3, "#34d399"),   # SG
    (139.7, 35.7, "#f5f5f4"),  # JP
    (149.1, -35.3, "#f5f5f4"), # AU
    (174.8, -41.3, "#34d399"), # NZ
]

ARCS: list[tuple[tuple[float, float], tuple[float, float]]] = [
    ((-77.0, 38.9), (-0.1, 51.5)),
    ((-0.1, 51.5), (36.8, -1.3)),
    ((-0.1, 51.5), (79.9, 6.9)),
    ((13.4, 52.5), (103.8, 1.3)),
    ((79.9, 6.9), (103.8, 1.3)),
    ((103.8, 1.3), (139.7, 35.7)),
    ((103.8, 1.3), (174.8, -41.3)),
    ((36.8, -1.3), (28.2, -25.7)),
]


def _point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1:
            inside = not inside
    return inside


def _proj(lon: float, lat: float, w: int = 1200, h: int = 675) -> tuple[float, float]:
    return (lon + 180.0) / 360.0 * w, (84.0 - lat) / 146.0 * h


def convert_ai_renders() -> None:
    for out_name, (src_path, max_w) in AI_SOURCES.items():
        if not src_path.exists():
            raise FileNotFoundError(f"Missing AI render source: {src_path}")
        pix = pymupdf.Pixmap(str(src_path))
        if pix.alpha or (pix.colorspace and pix.colorspace.n != 3):
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        if pix.width > max_w:
            scale = max_w / pix.width
            pix = pymupdf.Pixmap(pix, int(pix.width * scale), int(pix.height * scale))
        out_path = IMG_DIR / out_name
        out_path.write_bytes(pix.tobytes("jpeg", jpg_quality=88))


def svg_coverage_world() -> str:
    w, h = 1200, 675
    dots: list[str] = []
    for px in range(14, w - 10, 10):
        for py in range(14, h - 14, 10):
            lon = px / w * 360.0 - 180.0
            lat = 84.0 - py / h * 146.0
            if any(_point_in_poly(lon, lat, poly) for poly in CONTINENTS):
                dots.append(f'<circle cx="{px}" cy="{py}" r="1.8" fill="#575652" opacity="0.82"/>')

    grat: list[str] = []
    for gx in range(120, w, 120):
        grat.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{h}" stroke="#222220" stroke-width="1"/>')
    for gy in range(90, h, 90):
        grat.append(f'<line x1="0" y1="{gy}" x2="{w}" y2="{gy}" stroke="#222220" stroke-width="1"/>')

    arcs: list[str] = []
    for (lon1, lat1), (lon2, lat2) in ARCS:
        x1, y1 = _proj(lon1, lat1, w, h)
        x2, y2 = _proj(lon2, lat2, w, h)
        mx = (x1 + x2) / 2
        my = min(y1, y2) - max(42.0, abs(x2 - x1) * 0.16)
        arcs.append(
            f'<path d="M {x1:.1f} {y1:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}" '
            f'fill="none" stroke="url(#arcGrad)" stroke-width="1.6" opacity="0.6"/>'
        )

    hubs: list[str] = []
    for lon, lat, color in ACTIVE_HUBS:
        x, y = _proj(lon, lat, w, h)
        hubs.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="{color}" opacity="0.16"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="none" stroke="{color}" stroke-width="1.2" opacity="0.7"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{color}"/>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Global jurisdiction coverage">
  <defs>
    <radialGradient id="mapGlow" cx="55%" cy="45%" r="60%">
      <stop offset="0%" stop-color="#262624" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#141413" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="arcGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#e5e5e0"/>
      <stop offset="50%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#34d399"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="#141413"/>
  <rect width="{w}" height="{h}" fill="url(#mapGlow)"/>
  <g>{"".join(grat)}</g>
  <g>{"".join(dots)}</g>
  <g>{"".join(arcs)}</g>
  <g>{"".join(hubs)}</g>
</svg>
"""


def main() -> int:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    convert_ai_renders()
    (IMG_DIR / "coverage-world.svg").write_text(svg_coverage_world(), encoding="utf-8")
    for path in sorted(IMG_DIR.iterdir()):
        print(f"{path.name}: {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
