# CTO handover — Phase 1F

Implementation commit: `4b1296c`

Implemented a custom GazetteRegistry seal mark and stacked wordmark, self-hosted Inter typography, navy/white/blue and orange-accent commercial design, universal search hero with category scopes, prominent latest procurement opportunities, six entry points, compact coverage band, provenance section, responsive navigation and a footer with the independent-registry disclaimer. Inner pages share the same system. Detailed coverage and source statistics stay on their dedicated pages. Added deterministic `npm run package`, producing production and preview ZIPs with root `index.html`, SHA-256 manifests, integrity checks and standalone HTTP verification.

Validation: `npm test` 14/14 passed; production build 1,306 files, 10.36 MiB, 631 HTML pages, 630 sitemap URLs; preview 90 files, 35 noindex pages; Pagefind name and gazette queries passed; browser checks passed at 390–1440 px, including search scopes, mobile navigation and no horizontal overflow; repeated packaging was byte-identical.

Production ZIP: 4.197 MiB, 1,306 files, largest 344.0 KiB, SHA-256 `da9bbaedb5a2bfee5273697664c234a65f5215325c389357bb725e7daeb15e12`. Preview ZIP: 0.752 MiB, 90 files, SHA-256 `0c811ff5b000e7e46fb12c52567924e33522d6a31c2904c3b2dc51ca7ac08fa2`. Workers static assets compatible; Pages/Drop is not (306 files over its 1,000-file limit). The complete archive is preserved, not trimmed.

Screenshots: `reports/phase1f/home-desktop.png`, `home-mobile.png`, `home-mobile-menu.png`, `search-tenders.png`.

Limitations: local verification only; no deployment performed. Manual deployment remains outstanding.
