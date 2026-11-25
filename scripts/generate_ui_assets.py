"""Generate compressed JPGs from AI studio renders and bespoke dark-obsidian SVG visuals."""

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
    (-0.1, 51.5, "#60a5fa"),   # UK
    (-6.3, 53.3, "#60a5fa"),   # IE
    (4.9, 52.4, "#60a5fa"),    # NL
    (13.4, 52.5, "#60a5fa"),   # DE
    (-77.0, 38.9, "#34d399"),  # US
    (-75.7, 45.4, "#60a5fa"),  # CA
    (36.8, -1.3, "#f59e0b"),   # KE
    (28.2, -25.7, "#f59e0b"),  # ZA
    (79.9, 6.9, "#f59e0b"),    # LK
    (73.5, 4.2, "#34d399"),    # MV
    (90.4, 23.8, "#f59e0b"),   # BD
    (103.8, 1.3, "#34d399"),   # SG
    (139.7, 35.7, "#60a5fa"),  # JP
    (149.1, -35.3, "#60a5fa"), # AU
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
    for px in range(18, w - 12, 16):
        for py in range(18, h - 18, 16):
            lon = px / w * 360.0 - 180.0
            lat = 84.0 - py / h * 146.0
            if any(_point_in_poly(lon, lat, poly) for poly in CONTINENTS):
                dots.append(f'<circle cx="{px}" cy="{py}" r="1.9" fill="#254772"/>')

    grat: list[str] = []
    for gx in range(120, w, 120):
        grat.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{h}" stroke="#0f233e" stroke-width="1"/>')
    for gy in range(90, h, 90):
        grat.append(f'<line x1="0" y1="{gy}" x2="{w}" y2="{gy}" stroke="#0f233e" stroke-width="1"/>')

    arcs: list[str] = []
    for (lon1, lat1), (lon2, lat2) in ARCS:
        x1, y1 = _proj(lon1, lat1, w, h)
        x2, y2 = _proj(lon2, lat2, w, h)
        mx = (x1 + x2) / 2
        my = min(y1, y2) - max(40.0, abs(x2 - x1) * 0.16)
        arcs.append(
            f'<path d="M {x1:.1f} {y1:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}" '
            f'fill="none" stroke="url(#arcGrad)" stroke-width="1.6" stroke-dasharray="4 4" opacity="0.8"/>'
        )

    hubs: list[str] = []
    for lon, lat, color in ACTIVE_HUBS:
        x, y = _proj(lon, lat, w, h)
        hubs.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{color}" opacity="0.16"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="none" stroke="{color}" stroke-width="1.2" opacity="0.65"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{color}"/>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Global jurisdiction coverage">
  <defs>
    <radialGradient id="mapGlow" cx="55%" cy="45%" r="60%">
      <stop offset="0%" stop-color="#1d4ed8" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="#060e1a" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="arcGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#60a5fa"/>
      <stop offset="50%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#34d399"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="#060e1a"/>
  <rect width="{w}" height="{h}" fill="url(#mapGlow)"/>
  <g>{"".join(grat)}</g>
  <g>{"".join(dots)}</g>
  <g>{"".join(arcs)}</g>
  <g>{"".join(hubs)}</g>
</svg>
"""


def svg_workflow_pdfs() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500" role="img" aria-label="Layered gazette PDFs">
  <defs>
    <radialGradient id="pdfGlow" cx="50%" cy="50%" r="55%">
      <stop offset="0%" stop-color="#2563eb" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="#081326" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="sheetStroke" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#93c5fd" stop-opacity="0.75"/>
      <stop offset="100%" stop-color="#f59e0b" stop-opacity="0.55"/>
    </linearGradient>
    <linearGradient id="beam" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#60a5fa" stop-opacity="0"/>
      <stop offset="50%" stop-color="#60a5fa" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="800" height="500" fill="#081326"/>
  <rect width="800" height="500" fill="url(#pdfGlow)"/>
  <g stroke="#13294b" stroke-width="1">
    <path d="M0 100H800M0 200H800M0 300H800M0 400H800M160 0V500M320 0V500M480 0V500M640 0V500"/>
  </g>
  <g transform="translate(400 265)">
    <g transform="translate(0 72)">
      <polygon points="0,-95 190,-10 0,75 -190,-10" fill="#0f2544" fill-opacity="0.7" stroke="#284c7e" stroke-width="1.4"/>
    </g>
    <g transform="translate(0 28)">
      <polygon points="0,-95 190,-10 0,75 -190,-10" fill="#132d52" fill-opacity="0.75" stroke="#3b82f6" stroke-opacity="0.5" stroke-width="1.4"/>
    </g>
    <g transform="translate(0 -16)">
      <polygon points="0,-95 190,-10 0,75 -190,-10" fill="#173866" fill-opacity="0.8" stroke="#60a5fa" stroke-opacity="0.7" stroke-width="1.6"/>
    </g>
    <g transform="translate(0 -60)">
      <polygon points="0,-95 190,-10 0,75 -190,-10" fill="#1b4379" fill-opacity="0.86" stroke="url(#sheetStroke)" stroke-width="2"/>
      <line x1="-95" y1="-22" x2="35" y2="36" stroke="#93c5fd" stroke-width="3" stroke-linecap="round" opacity="0.65"/>
      <line x1="-65" y1="-44" x2="65" y2="14" stroke="#cbd5e1" stroke-width="2.5" stroke-linecap="round" opacity="0.45"/>
      <line x1="-35" y1="-64" x2="95" y2="-6" stroke="#f59e0b" stroke-width="3" stroke-linecap="round" opacity="0.8"/>
    </g>
  </g>
  <rect x="398" y="34" width="4" height="430" fill="url(#beam)"/>
</svg>
"""


def svg_workflow_index() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500" role="img" aria-label="Cross-publisher structured indexing">
  <defs>
    <radialGradient id="idxGlow" cx="46%" cy="50%" r="48%">
      <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="#081326" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="lineIn" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#60a5fa" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#60a5fa" stop-opacity="0.9"/>
    </linearGradient>
  </defs>
  <rect width="800" height="500" fill="#081326"/>
  <rect width="800" height="500" fill="url(#idxGlow)"/>
  <g stroke="url(#lineIn)" stroke-width="2" fill="none">
    <path d="M90 110 C 210 110, 240 250, 355 250"/>
    <path d="M120 195 C 225 195, 250 250, 355 250"/>
    <path d="M80 305 C 215 305, 250 250, 355 250"/>
    <path d="M135 390 C 230 390, 250 250, 355 250"/>
  </g>
  <g fill="#60a5fa">
    <circle cx="90" cy="110" r="6"/><circle cx="120" cy="195" r="6" fill="#f59e0b"/>
    <circle cx="80" cy="305" r="6"/><circle cx="135" cy="390" r="6" fill="#34d399"/>
  </g>
  <g stroke="#34d399" stroke-width="2" fill="none" opacity="0.85">
    <path d="M445 250 C 495 250, 505 130, 545 130"/>
    <path d="M445 250 C 495 250, 505 210, 545 210" stroke="#60a5fa"/>
    <path d="M445 250 C 495 250, 505 290, 545 290" stroke="#f59e0b"/>
    <path d="M445 250 C 495 250, 505 370, 545 370" stroke="#93c5fd"/>
  </g>
  <polygon points="400,190 456,250 400,310 344,250" fill="#132e56" stroke="#93c5fd" stroke-width="2"/>
  <polygon points="400,214 434,250 400,286 366,250" fill="#2563eb" fill-opacity="0.45" stroke="#f59e0b" stroke-width="1.5"/>
  <g>
    <rect x="545" y="106" width="175" height="48" rx="10" fill="#0f2544" stroke="#284c7e" stroke-width="1.5"/>
    <circle cx="570" cy="130" r="5" fill="#34d399"/>
    <rect x="588" y="124" width="106" height="12" rx="6" fill="#cbd5e1" opacity="0.65"/>

    <rect x="545" y="186" width="175" height="48" rx="10" fill="#0f2544" stroke="#284c7e" stroke-width="1.5"/>
    <circle cx="570" cy="210" r="5" fill="#60a5fa"/>
    <rect x="588" y="204" width="92" height="12" rx="6" fill="#cbd5e1" opacity="0.65"/>

    <rect x="545" y="266" width="175" height="48" rx="10" fill="#0f2544" stroke="#284c7e" stroke-width="1.5"/>
    <circle cx="570" cy="290" r="5" fill="#f59e0b"/>
    <rect x="588" y="284" width="112" height="12" rx="6" fill="#cbd5e1" opacity="0.65"/>

    <rect x="545" y="346" width="175" height="48" rx="10" fill="#0f2544" stroke="#284c7e" stroke-width="1.5"/>
    <circle cx="570" cy="370" r="5" fill="#93c5fd"/>
    <rect x="588" y="364" width="84" height="12" rx="6" fill="#cbd5e1" opacity="0.65"/>
  </g>
</svg>
"""


def svg_workflow_deadlines() -> str:
    ticks: list[str] = []
    import math
    for deg in range(0, 360, 15):
        rad = math.radians(deg)
        r1 = 152
        r2 = 166 if deg % 45 == 0 else 160
        x1, y1 = 400 + r1 * math.cos(rad), 250 + r1 * math.sin(rad)
        x2, y2 = 400 + r2 * math.cos(rad), 250 + r2 * math.sin(rad)
        ticks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#475569" stroke-width="2"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500" role="img" aria-label="Precision closing deadline dial">
  <defs>
    <radialGradient id="dialGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#f59e0b" stop-opacity="0.22"/>
      <stop offset="55%" stop-color="#2563eb" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#081326" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="amberArc" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fbbf24"/>
      <stop offset="100%" stop-color="#ef7d1a"/>
    </linearGradient>
  </defs>
  <rect width="800" height="500" fill="#081326"/>
  <rect width="800" height="500" fill="url(#dialGlow)"/>
  <circle cx="400" cy="250" r="184" fill="none" stroke="#1e3a5f" stroke-width="1.5" stroke-dasharray="6 6"/>
  <circle cx="400" cy="250" r="140" fill="#0d1e36" stroke="#284c7e" stroke-width="2"/>
  <circle cx="400" cy="250" r="98" fill="none" stroke="#1e3a5f" stroke-width="1.5"/>
  <g>{"".join(ticks)}</g>
  <path d="M 400 110 A 140 140 0 0 1 524 316" fill="none" stroke="url(#amberArc)" stroke-width="8" stroke-linecap="round"/>
  <line x1="400" y1="250" x2="495" y2="188" stroke="#f8fafc" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="524" cy="316" r="9" fill="#ef7d1a"/>
  <circle cx="524" cy="316" r="18" fill="#ef7d1a" opacity="0.22"/>
  <circle cx="400" cy="250" r="12" fill="#1e3a5f" stroke="#93c5fd" stroke-width="2.5"/>
</svg>
"""


def svg_bento_procurement() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500" role="img" aria-label="Procurement opportunity pipeline">
  <defs>
    <radialGradient id="procGlow" cx="65%" cy="35%" r="60%">
      <stop offset="0%" stop-color="#2563eb" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="#071222" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="800" height="500" fill="#071222"/>
  <rect width="800" height="500" fill="url(#procGlow)"/>
  <g>
    <rect x="76" y="72" width="648" height="96" rx="14" fill="#0e223d" stroke="#284c7e" stroke-width="1.5"/>
    <circle cx="116" cy="120" r="9" fill="#10b981"/>
    <rect x="148" y="102" width="290" height="14" rx="7" fill="#e2e8f0" opacity="0.82"/>
    <rect x="148" y="128" width="180" height="10" rx="5" fill="#64748b" opacity="0.7"/>
    <rect x="576" y="104" width="112" height="32" rx="16" fill="#2563eb" fill-opacity="0.28" stroke="#60a5fa" stroke-width="1.2"/>

    <rect x="76" y="198" width="648" height="96" rx="14" fill="#112a4b" stroke="#3b82f6" stroke-opacity="0.65" stroke-width="1.8"/>
    <circle cx="116" cy="246" r="9" fill="#10b981"/>
    <rect x="148" y="228" width="340" height="14" rx="7" fill="#ffffff" opacity="0.92"/>
    <rect x="148" y="254" width="220" height="10" rx="5" fill="#93c5fd" opacity="0.65"/>
    <rect x="576" y="230" width="112" height="32" rx="16" fill="#ef7d1a" fill-opacity="0.24" stroke="#f59e0b" stroke-width="1.4"/>

    <rect x="76" y="324" width="648" height="96" rx="14" fill="#0e223d" stroke="#284c7e" stroke-width="1.5"/>
    <circle cx="116" cy="372" r="9" fill="#f59e0b"/>
    <rect x="148" y="354" width="250" height="14" rx="7" fill="#e2e8f0" opacity="0.78"/>
    <rect x="148" y="380" width="150" height="10" rx="5" fill="#64748b" opacity="0.7"/>
    <rect x="576" y="356" width="112" height="32" rx="16" fill="#10b981" fill-opacity="0.22" stroke="#34d399" stroke-width="1.2"/>
  </g>
</svg>
"""


def svg_bento_archive() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500" role="img" aria-label="Page-level gazette archive">
  <defs>
    <radialGradient id="archGlow" cx="50%" cy="45%" r="55%">
      <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#071222" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="800" height="500" fill="#071222"/>
  <rect width="800" height="500" fill="url(#archGlow)"/>
  <g>
    <rect x="96" y="76" width="296" height="348" rx="12" fill="#0e223d" stroke="#284c7e" stroke-width="1.5"/>
    <rect x="408" y="76" width="296" height="348" rx="12" fill="#112a4b" stroke="#60a5fa" stroke-opacity="0.65" stroke-width="1.8"/>
    <rect x="132" y="116" width="164" height="14" rx="7" fill="#93c5fd" opacity="0.8"/>
    <rect x="132" y="150" width="224" height="9" rx="4.5" fill="#64748b" opacity="0.65"/>
    <rect x="132" y="174" width="204" height="9" rx="4.5" fill="#64748b" opacity="0.65"/>
    <rect x="132" y="198" width="218" height="9" rx="4.5" fill="#64748b" opacity="0.65"/>
    <rect x="132" y="236" width="224" height="72" rx="8" fill="#16355e" stroke="#3b82f6" stroke-opacity="0.5"/>
    <rect x="132" y="330" width="186" height="9" rx="4.5" fill="#64748b" opacity="0.55"/>
    <rect x="132" y="354" width="146" height="9" rx="4.5" fill="#64748b" opacity="0.55"/>

    <rect x="444" y="116" width="182" height="14" rx="7" fill="#ffffff" opacity="0.88"/>
    <rect x="444" y="150" width="224" height="9" rx="4.5" fill="#94a3b8" opacity="0.6"/>
    <rect x="444" y="174" width="210" height="9" rx="4.5" fill="#94a3b8" opacity="0.6"/>
    <rect x="444" y="212" width="224" height="92" rx="8" fill="#173b68" stroke="#f59e0b" stroke-width="1.6"/>
    <circle cx="468" cy="236" r="6" fill="#10b981"/>
    <rect x="486" y="231" width="150" height="10" rx="5" fill="#e2e8f0" opacity="0.85"/>
    <rect x="462" y="260" width="180" height="9" rx="4.5" fill="#93c5fd" opacity="0.65"/>
    <rect x="444" y="334" width="150" height="32" rx="16" fill="#2563eb" fill-opacity="0.28" stroke="#60a5fa" stroke-width="1.2"/>
  </g>
</svg>
"""


def main() -> int:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    convert_ai_renders()
    svgs = {
        "coverage-world.svg": svg_coverage_world(),
        "workflow-pdfs.svg": svg_workflow_pdfs(),
        "workflow-index.svg": svg_workflow_index(),
        "workflow-deadlines.svg": svg_workflow_deadlines(),
        "bento-procurement.svg": svg_bento_procurement(),
        "bento-archive.svg": svg_bento_archive(),
    }
    for name, content in svgs.items():
        (IMG_DIR / name).write_text(content, encoding="utf-8")
    for path in sorted(IMG_DIR.iterdir()):
        print(f"{path.name}: {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
