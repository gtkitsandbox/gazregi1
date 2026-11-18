#!/usr/bin/env node
// Exercise the generated Pagefind index through an ephemeral local server.
// This is the same index and module the browser loads from /pagefind/.

import { createReadStream, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const args = process.argv.slice(2);
const preview = args.includes("--preview");
const siteIndex = args.indexOf("--site");
const site = resolve(siteIndex >= 0 ? args[siteIndex + 1] : preview ? "dist-preview" : "dist");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".wasm": "application/wasm",
  ".pf_meta": "application/octet-stream",
  ".pf_fragment": "application/octet-stream",
  ".pf_index": "application/octet-stream",
  ".xml": "application/xml; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
};

const server = createServer((request, response) => {
  let path = decodeURIComponent((request.url || "/").split("?")[0]);
  let file = join(site, normalize(path).replace(/^(\.\.[/\\])+/, ""));
  try {
    if (statSync(file).isDirectory()) file = join(file, "index.html");
    const stats = statSync(file);
    response.writeHead(200, {
      "Content-Type": MIME[extname(file)] || "application/octet-stream",
      "Content-Length": stats.size,
    });
    createReadStream(file).pipe(response);
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain" });
    response.end("not found");
  }
});

await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
const { port } = server.address();

try {
  const pagefind = await import(pathToFileURL(join(site, "pagefind", "pagefind.js")).href);
  await pagefind.options({ basePath: `http://127.0.0.1:${port}/pagefind/` });

  const expectations = preview
    ? [
        { term: "office stationery", includes: "/tenders/XX-2099-9999-TEND-001/" },
        { term: "Example Procurement Authority", includes: "/tenders/XX-2099-9999-TEND-001/" },
        { term: "A. Example", includes: "/people/xx/a-example-001/" },
        { term: "A. Example", includes: "/people/xx/a-example-002/" },
        { term: "Example Community Drainage Scheme", includes: "/tenders/XX-2099-9999-TEND-002/" },
      ]
    : [
        { term: "2502", includes: "/records/LK-2026-2502-" },
        { term: "Gazette", includes: "/gazettes/" },
      ];

  const failures = [];
  for (const expectation of expectations) {
    const response = await pagefind.search(expectation.term);
    const results = await Promise.all(response.results.map((result) => result.data()));
    const urls = results.map((result) => result.url);
    if (!urls.some((url) => url.includes(expectation.includes))) {
      failures.push(
        `query "${expectation.term}" did not return ${expectation.includes} (got ${urls.length} results)`,
      );
    }
    console.log(`  search "${expectation.term}": ${results.length} result(s)`);
  }

  if (failures.length) {
    for (const failure of failures) console.error(`SEARCH ERROR: ${failure}`);
    process.exitCode = 1;
  } else {
    console.log("Search validation passed.");
  }
} finally {
  server.close();
}
