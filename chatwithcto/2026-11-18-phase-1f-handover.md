# CTO handover — Phase 1F

Implementation commit: `866199d`

Implemented a visible GazetteRegistry wordmark, self-hosted Inter typography, navy/white/blue design system, universal search hero with people/organisation/gazette/tender scopes, problem-led homepage, latest open tenders, six entry points, compact coverage band, provenance section, responsive navigation and a footer with the independent-registry disclaimer. Detailed coverage and source statistics moved to their dedicated pages. Added deterministic `npm run package`, producing production and preview ZIPs with root `index.html`, SHA-256 manifests, integrity checks and standalone HTTP verification.

Validation: `npm test` 14/14 passed; production build 1,306 files, 10.15 MiB, 631 HTML pages, 630 sitemap URLs; preview 90 files, 35 noindex pages; Pagefind name and gazette queries passed; browser checks passed at 390–1440 px, including search scopes, mobile navigation and no horizontal overflow; both Wrangler dry runs exited 0; repeated packaging was byte-identical.

Production ZIP: 4.173 MiB, 1,306 files, largest 344.0 KiB, SHA-256 `f572e754009249fa381a8122ddef46505e2a00b9f26eb14445eb92ec8a664f2e`. Preview ZIP: 0.751 MiB, 90 files, SHA-256 `596c223a42d0a6bef41a86503bab9100bcf7675e9245c1ee873b635b8f750642`. Workers static assets compatible; Pages/Drop is not (306 files over its 1,000-file limit). The complete archive is preserved, not trimmed.

Screenshots: `reports/phase1f/home-desktop.png`, `home-mobile.png`, `home-mobile-menu.png`, `search-tenders.png`.

Limitations: local verification only; no deployment performed. Manual deployment remains outstanding.
