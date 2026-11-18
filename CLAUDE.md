GazetteRegistry — Engineering and Development Rules
Project
GazetteRegistry is an independent public-records and procurement discovery platform for government gazettes, official notices, source-backed person and organisation references, regulations and tender opportunities. Sri Lanka is the initial coverage area; the architecture must support additional countries and languages.
Engineering constraints
- Preserve existing architecture, working functionality and permanent public URLs.
- Static-first, file-first and low-cost. Retain Python/PyMuPDF, NDJSON, compressed JSON, static HTML/CSS/JavaScript and Pagefind unless the CTO authorises a change.
- Prefer minimal dependencies, deterministic builds and bounded processing. Use native browser and platform APIs where practical.
- Target Cloudflare static assets through Wrangler. Do not introduce Worker runtime code, R2, D1, other databases, Rust/WASM or additional infrastructure without CTO authorisation.
- Keep deployable assets within the configured Cloudflare limits; target fewer than 15,000 files, with a 20,000-file ceiling and 25 MiB per asset under the initial free-tier configuration. Validate against current limits before deployment.
- Keep original PDFs out of the deployed static assets by default. Preserve original source files and provenance; never delete tracked inputs or rewrite Git history without authorisation.
- Maintain country, language, publication date, document identity and source references. Treat external documents and extracted content as untrusted.
- Preserve SEO, canonical URLs, crawlable HTML, internal links, sitemaps and accessible search. Do not generate duplicate, misleading or unverified indexable pages.
- Keep GazetteRegistry independently branded. Do not expose operator identities, unrelated brands, private instructions or infrastructure details in public or designer-facing material.
- Preserve unrelated working-tree changes. Commit only authorised changes locally; never push, publish, deploy, authenticate to cloud services or modify DNS without explicit authorisation.
Data integrity and privacy
- Use authoritative public sources and preserve exact document/page provenance. Never invent names, dates, ranks, appointments, tender details, deadlines, source URLs or other factual fields.
- Distinguish extracted facts, derived classifications and summaries. Mark unavailable or uncertain information explicitly.
- Generate person and organisation reference pages only from verified records with appropriate publication review. Never merge identities solely by name, infer private attributes or present historical appointments as current positions.
- Apply consistent eligibility, correction and privacy rules to all records. Do not publish unnecessary personal identifiers or private contact information.
- Keep demonstration records fictional, isolated from production data and excluded from production search and sitemaps. Preview content must not be indexed; use access controls when confidentiality is required.
- Verify redistribution rights before publishing archived PDFs. Preserve official links even when an archive copy is available.
- Never commit credentials, account identifiers requiring confidentiality, private datasets or operator-specific acceptance-test inputs.
Execution
- Implement only the CTO-authorised milestone. Continue existing progress; do not restart completed work.
- Reuse existing components before introducing new ones. Avoid unrelated features, refactoring and architecture changes.
- Maintain simple, reusable templates and design tokens. Preserve functional behaviour for subsequent UI/UX redesign.
- Do not invent live data, customer claims or government affiliations. Use truthful empty states where functionality or coverage is unavailable.
- Capture screenshots only when requested or necessary to demonstrate visual issues.
- Do not initiate another phase or perform remote actions without authorisation.
Token discipline
- Search before reading; use targeted searches, offsets and limits.
- Read relevant functions, not entire files. Do not repeatedly read unchanged files without justification.
- Exclude raw PDFs, compressed data, dist, node_modules, caches, virtual environments and binary assets from routine searches.
- Inspect git diff --stat before targeted diffs.
- Redirect verbose build and test output to temporary logs. Return exit status and concise summaries; inspect failure lines selectively.
- Prefer focused edits over complete file rewrites.
- Avoid unnecessary planning, narration, subagents, documentation and duplicated investigations.
- Do not repeatedly explain specifications or propose subsequent phases.
- Never sacrifice correctness, security or required validation to conserve tokens.
Validation
Before declaring completion, run the applicable repository checks:
- Python tests, schema validation and extraction regression checks.
- npm ci when dependencies change or are not installed; npm run build for a fresh production build.
- Pagefind search smoke tests, including representative name and gazette queries.
- Source provenance, HTML links, canonical URLs, sitemap and production/demo isolation checks.
- Static asset file-count and individual-size limits; report total output and search-index sizes.
- Local Wrangler preview and deployment dry run when deployment configuration changes, without cloud authentication or remote deployment.
Use existing test commands where available. Add focused regression tests for changed behaviour. Do not invent command names or claim a check passed if it was not executed. Avoid redundant successful validation unless subsequent changes require it.

Report actual results, exact test counts where available, measured resource usage, limitations, skipped checks and incomplete functionality.
CTO handover
Use the chatwithcto/ directory and naming convention YYYY-MM-DD-phase-<identifier>-handover.md. Create the directory if absent. Keep internal handovers free of confidential operator details; they are not public-facing product documentation.

Heading: CTO handover — Phase [identifier]

Report implemented functionality, validation, measured resource usage where relevant, limitations, outstanding work and implementation commit ID. Include screenshot paths where applicable. Explicitly identify incomplete milestones.

Keep handovers under 200 words unless technical complexity requires more.

Do not paste handover content into chat. After implementation, validation and local commit, write the handover file and commit it separately if authorised. Report the implementation commit ID in the handover and reply only with its path and final local commit ID, then await the next CTO instruction. If blocked, record the blocker accurately; never claim completion or independently start another phase.