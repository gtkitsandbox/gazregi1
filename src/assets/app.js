const pagefindImport = "/pagefind/pagefind.js";
let pagefind;
let latestSearch = 0;

function initSiteSearch() {
  const form = document.querySelector("#search-form");
  const input = document.querySelector("#search-query");
  const results = document.querySelector("#search-results");
  const count = document.querySelector("#result-count");
  if (!form || !input || !results || !count) return;

  const initialResults = results.innerHTML;
  const initialCount = count.textContent;

  async function runSearch(query) {
    const requestId = ++latestSearch;
    const trimmed = query.trim();
    if (!trimmed) {
      results.innerHTML = initialResults;
      count.textContent = initialCount;
      return;
    }

    count.textContent = "Searching...";
    try {
      if (!pagefind) pagefind = await import(pagefindImport);
      const response = await pagefind.search(trimmed);
      const matches = await Promise.all(response.results.map((result) => result.data()));
      if (requestId !== latestSearch) return;

      results.replaceChildren(...matches.map(renderResult));
      count.textContent = `${matches.length} ${matches.length === 1 ? "result" : "results"} for “${trimmed}”`;
      if (matches.length === 0) {
        const empty = document.createElement("p");
        empty.className = "empty-state";
        empty.textContent = "No indexed pages match this search.";
        results.append(empty);
      }
    } catch {
      count.textContent = "Search index could not be loaded. Try refreshing the page.";
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch(input.value);
  });

  input.addEventListener("input", () => {
    window.clearTimeout(input.searchTimer);
    input.searchTimer = window.setTimeout(() => runSearch(input.value), 160);
  });

  const query = new URLSearchParams(window.location.search).get("q");
  if (query) {
    input.value = query;
    runSearch(query);
  }
}

function renderResult(result) {
  const card = document.createElement("article");
  card.className = "record-card";

  const top = document.createElement("div");
  top.className = "record-card__top";
  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = "Indexed page";
  top.append(badge);

  const title = document.createElement("h3");
  title.className = "record-card__title";
  const link = document.createElement("a");
  link.href = result.url;
  link.textContent = result.meta?.title?.replace(/\s*\|\s*GazetteRegistry\s*$/, "") || "Indexed page";
  title.append(link);

  const excerpt = document.createElement("p");
  excerpt.className = "record-card__summary";
  excerpt.innerHTML = result.excerpt;

  card.append(top, title, excerpt);
  return card;
}

function initTenderFilters() {
  const form = document.querySelector("[data-tender-filters]");
  const list = document.querySelector("[data-tender-list]");
  const empty = document.querySelector("[data-tender-empty]");
  const count = document.querySelector("#tender-count");
  if (!form || !list || !empty || !count) return;

  const cards = Array.from(list.querySelectorAll("[data-tender]"));
  const queryInput = form.querySelector('[data-filter="query"]');
  const selects = Array.from(form.querySelectorAll("select[data-filter]"));

  function closingState(card) {
    const value = card.dataset.closing;
    if (!value) return "unknown";
    const time = card.dataset.closingTime || "23:59";
    const closing = new Date(`${value}T${time}`);
    if (Number.isNaN(closing.getTime())) return "unknown";
    const now = new Date();
    if (closing < now) return "closed";
    const days = (closing - now) / 86400000;
    return days <= 30 ? "soon" : "open";
  }

  function applyFilters() {
    const query = (queryInput?.value || "").trim().toLowerCase();
    const values = Object.fromEntries(
      selects.map((select) => [select.dataset.filter, select.value]),
    );
    let visible = 0;

    for (const card of cards) {
      const haystack = card.textContent.toLowerCase();
      const matchesQuery = !query || haystack.includes(query);
      const matchesSector = !values.sector || card.dataset.sector === values.sector;
      const matchesLocation = !values.location || card.dataset.location === values.location;
      const matchesOrganisation =
        !values.organisation || card.dataset.organisation === values.organisation;
      const state = closingState(card);
      const matchesClosing =
        !values.closing ||
        values.closing === state ||
        (values.closing === "open" && (state === "open" || state === "soon"));
      const show =
        matchesQuery && matchesSector && matchesLocation && matchesOrganisation && matchesClosing;
      card.hidden = !show;
      if (show) visible += 1;
    }

    count.textContent = `${visible} ${visible === 1 ? "tender" : "tenders"}`;
    empty.hidden = visible !== 0;
  }

  form.addEventListener("input", applyFilters);
  form.addEventListener("change", applyFilters);
  form.addEventListener("reset", () => window.setTimeout(applyFilters, 0));
  applyFilters();
}

initSiteSearch();
initTenderFilters();
