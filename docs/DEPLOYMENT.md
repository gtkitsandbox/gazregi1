# Deployment

The site is a fully static export of `dist/`. No Worker script, database, KV namespace, R2 bucket or server runtime is required.

## 1. Local setup

```bash
python -m pip install -r requirements.txt
npm ci
```

Wrangler is pinned to an exact version in `package.json` (`4.164.0`) and declared as a development dependency.

## 2. Production build

```bash
npm run build
```

This runs, in order:

1. `scripts/build_site.py` → writes `dist/`.
2. `pagefind --site dist` → writes `dist/pagefind/`.
3. `scripts/validate_site.py` → SEO, links, provenance, content and Cloudflare limits.
4. `scripts/validate_search.mjs` → real Pagefind queries against a local server.

The build fails on any validation error. Do not deploy a build that has not completed successfully.

Set `SITE_URL` only for a non-production canonical host:

```bash
SITE_URL=https://staging.example.com npm run build
```

The default is `https://gazetteregistry.com`, read from `config/site.json`.

## 3. Build outputs

| Path | Purpose |
| --- | --- |
| `dist/` | Production asset directory |
| `dist/pagefind/` | Prebuilt search index |
| `dist/sitemap.xml` | Canonical production URLs |
| `dist/robots.txt` | Allows crawling and references the sitemap |
| `dist/CNAME` | GitHub Pages custom domain (retained for the existing workflow) |
| `dist/_headers` | Static security headers |
| `dist/404.html` | Static not-found page |
| `dist/countries/` | Alphabetical country coverage index and per-country pages |
| `dist/sources/` | Official source registry with access status and notes |

`dist/` is ignored by Git. It is reproducible from tracked sources.

### Manual static ZIP packages

```bash
npm run package
```

This rebuilds production and preview, then runs `scripts/package_release.py`. It writes:

| Archive | Source | Contents |
| --- | --- | --- |
| `release/gazetteregistry-production.zip` | `dist/` | Complete production site, including sitemap and CNAME |
| `release/gazetteregistry-preview.zip` | `dist-preview/` | Fictional designer preview only; no production data |

`index.html` is at the ZIP root — there is no enclosing `dist` directory. HTML, CSS, JavaScript, the self-hosted font, `_headers`, `robots.txt`, `404.html`, favicon, Pagefind index and public deployment files are included. PDFs, Python source, NDJSON/compressed data, Git metadata, internal documentation, CTO handovers, credentials, private verification material, `node_modules` and development configuration are excluded; packaging fails if any are found.

Archives use sorted entries, a fixed `1980-01-01` timestamp and fixed file modes, so repeated packaging of an unchanged build is byte-identical. Each run verifies ZIP integrity, required files, root `index.html`, unsafe paths, file count, largest asset, SHA-256 archive and manifest checksums. It then extracts each archive into a temporary directory and serves it independently over HTTP to confirm key pages and assets return 200.

Phase 1F measurements:

| Package | ZIP size | Files | Largest asset | Pages upload | Workers assets |
| --- | --- | --- | --- | --- | --- |
| Production | 4.197 MiB | 1,306 | 344.0 KiB | Not compatible (306 over 1,000) | Compatible |
| Preview | 0.752 MiB | 90 | 344.0 KiB | Compatible | Compatible |

Cloudflare Pages direct upload, including Cloudflare Drop, currently caps a deployment at **1,000 files**. The complete production archive exceeds that by 306 files. Do not remove records, permanent pages or Pagefind shards to fit: preserve the complete archive and deploy it through a path that supports the full file count (Workers static assets, or a Pages Git integration if its current limits allow). `release/` is not tracked by Git.

## 4. Validation only

```bash
npm run validate          # validate existing dist/
npm run validate:preview  # validate existing dist-preview/
npm run validate:search   # Pagefind queries for dist/
npm run validate:search:preview
```

Validation reports:

- generated file count and total output size;
- largest generated file;
- Pagefind index size and file count;
- every HTML page missing a title, description, canonical, `h1`, robots directive or valid JSON-LD;
- broken internal links and missing local assets;
- record provenance re-check;
- verified/unverified person page presence;
- preview isolation (noindex, no sitemap, no production markers);
- production leakage of demo markers.

## 5. Local Wrangler preview

```bash
npm run preview
```

Runs `wrangler dev` against `./dist` using `wrangler.jsonc`. Wrangler serves the static assets and applies:

```jsonc
"assets": {
  "directory": "./dist",
  "not_found_handling": "404-page"
}
```

Verified locally:

- `/` → HTTP 200;
- unknown path → HTTP 404 served from the generated `dist/404.html`;
- `/pagefind/pagefind.js` → HTTP 200;
- `_headers` parsed as a valid header rule.

If Wrangler is unavailable, a plain static server also works:

```bash
npm run preview:serve
```

No Cloudflare account, token, DNS record or remote resource is used by any build or validation command.

## 6. Designer preview deployment

The preview is a separate static output and a separate Wrangler project. It is built from `demo/` and `config/preview.json`, never from production `data/`:

```bash
npm run build:preview          # dist-preview/, noindex, no sitemap, no CNAME
npm run preview:designer       # wrangler dev --config wrangler.preview.jsonc
npm run deploy:preview         # operator-only; requires Cloudflare authentication
```

`wrangler.preview.jsonc` uses the project name `gazetteregistry-designer-preview` and serves `./dist-preview`. Production `wrangler.jsonc` is unchanged and serves `./dist`.

Preview content is fictional, excluded from the production sitemap and search index, and carries `noindex` plus a visible preview banner. **`noindex` is not access control.** Before sharing a deployed preview, restrict access with one of:

- Cloudflare Access in front of the preview host (email allow-list or one-time PIN);
- a separate `*.pages.dev`/preview host that is not linked or submitted for indexing;
- HTTP Basic authentication at the edge.

Do not place internal project information, credentials or production corrections data in `demo/`. The validator rejects preview data in the production build and production markers in the preview build.

## 7. Deploying (operator action, not performed in Phase 1F)

Run these commands from the repository root. The dry run does not authenticate or upload:

```bash
npm ci
npm test
npm run build
npm run build:preview
npx wrangler deploy --dry-run
npx wrangler deploy --dry-run --config wrangler.preview.jsonc
```

After reviewing the dry run, authenticate and deploy production only:

```bash
npx wrangler login          # or set a scoped CLOUDFLARE_API_TOKEN
npx wrangler deploy         # serves ./dist via wrangler.jsonc
```

`npm run deploy` is a convenience wrapper for the last command. Do not commit credentials, `.env` files or `wrangler` authentication state.

### Custom-domain verification

Configure the production custom domain in the Cloudflare dashboard under Workers & Pages → the production project → Custom domains. Do not change DNS until that step is authorised. Verify after propagation:

```bash
dig +short gazetteregistry.com
dig +short www.gazetteregistry.com
curl -sSI https://gazetteregistry.com/ | head -n 5
curl -sS https://gazetteregistry.com/robots.txt
curl -sS https://gazetteregistry.com/sitemap.xml | head -n 5
curl -sS -o /dev/null -w '%{http_code}\n' https://gazetteregistry.com/does-not-exist/
```

`nslookup` is an acceptable substitute if `dig` is unavailable. Confirm the canonical host in the generated HTML matches the verified domain.

### Corrections configuration

The corrections page is built and ready. To enable the operator's submission route, set the public values in `config/site.json` and rebuild:

```json
"corrections_email": "operator-configured-public-address",
"corrections_note": "Optional public handling note"
```

Until configured, the page truthfully states that no public submission channel has been enabled. Do not put private verification evidence or operator identity in these fields.

### Cutover checklist

1. Confirm `npm test`, `npm run build` and `npm run build:preview` pass.
2. Confirm both Wrangler dry runs succeed and `dist/` contains no PDFs, credentials or internal documentation.
3. Enable the corrections contact route and rebuild production.
4. Configure the custom domain in Cloudflare and verify DNS, `/`, `/robots.txt`, `/sitemap.xml` and a missing path.
5. Keep the GitHub Pages workflow active until the Cloudflare deployment is verified, then disable it with explicit authorisation.
6. Submit the sitemap to search engines only after cutover is confirmed.

## 8. Cloudflare static limits

Wrangler static assets have hard limits: **20,000 files** and **25 MiB per file**. The project targets **fewer than 15,000 files**. `scripts/validate_site.py` fails above 20,000, warns above 15,000 and reports the largest file.

For reference, the Phase 1F production build produced 1,306 files and 10.36 MiB total; the Pagefind index is 666 files and 1.84 MiB. Growth is dominated by HTML pages and the search index, not PDFs; no PDFs are copied into `dist/`.

If a future dataset approaches the limit, split by country into separate deployments or move non-page assets to object storage. Neither is implemented; both require CTO authorisation.

## 9. GitHub Pages

`.github/workflows/deploy.yml` builds and deploys production on pushes to `main`. A separate `preview` job builds and validates `dist-preview/` without deploying it. Phase 1E made a local commit only; nothing was pushed, so the workflow has not run.

## 10. Rollback

Because `dist/` is generated, rollback is a rebuild of the previous commit followed by redeployment. Source PDFs and curated NDJSON are tracked, so every published page can be regenerated from the repository plus the local `raw/` inputs.

Preferred rollback is the Cloudflare dashboard's deployment history: select the last known-good deployment and roll back. Rebuild-based rollback:

```bash
git log --oneline -n 5
git switch --detach <last-known-good-commit>
npm ci
npm run build
npx wrangler deploy
```

Return to the release branch afterwards with `git switch main`. Keep the previous deployment available until the replacement is verified.
