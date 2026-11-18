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

## 6. Deploying (operator action, not performed in Phase 1B)

```bash
npm run build
npm run validate
npx wrangler deploy
```

`npm run deploy` is a convenience wrapper for `wrangler deploy`. The operator must authenticate first (`npx wrangler login` or a scoped `CLOUDFLARE_API_TOKEN`). Do not commit credentials or `.env` files.

### Cutover checklist

1. Confirm `npm run build` and `npm run validate` pass.
2. Confirm the generated canonical host matches the intended production host.
3. Confirm `sitemap.xml` URLs resolve.
4. Configure the custom domain in Cloudflare.
5. Verify `/` and a deliberately missing path in production.
6. Keep the GitHub Pages workflow active until the Cloudflare deployment is verified, then disable it with explicit authorisation.
7. Submit the sitemap to search engines only after cutover is confirmed.

## 7. Cloudflare static limits

Wrangler static assets have hard limits: **20,000 files** and **25 MiB per file**. Phase 1B targets **fewer than 15,000 files**. `scripts/validate_site.py` fails above 20,000, warns above 15,000 and reports the largest file.

For reference, the Phase 1B production build produced roughly 444 files and 3.1 MiB total. Growth is dominated by HTML pages, not PDFs; no PDFs are copied into `dist/`.

If a future dataset approaches the limit, split by country into separate deployments or move non-page assets to R2. Neither is implemented in Phase 1B.

## 8. GitHub Pages

`.github/workflows/deploy.yml` is unchanged and still builds/deploys the site on pushes to `main`. Phase 1B made a local commit only; nothing was pushed, so the workflow has not run.

## 9. Rollback

Because `dist/` is generated, rollback is a rebuild of the previous commit followed by redeployment. Source PDFs and curated NDJSON are tracked, so every published page can be regenerated from the repository plus the local `raw/` inputs.
