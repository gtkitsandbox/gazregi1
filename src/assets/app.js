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
      const matchesCountry = !values.country || card.dataset.country === values.country;
      const state = closingState(card);
      const matchesClosing =
        !values.closing ||
        values.closing === state ||
        (values.closing === "open" && (state === "open" || state === "soon"));
      const show =
        matchesQuery && matchesSector && matchesLocation && matchesOrganisation && matchesCountry && matchesClosing;
      card.hidden = !show;
      if (show) visible += 1;
    }

    count.textContent = `${visible} ${visible === 1 ? "tender" : "tenders"}`;
    empty.hidden = visible !== 0;
  }

  form.addEventListener("input", applyFilters);
  form.addEventListener("change", applyFilters);
  form.addEventListener("reset", () => window.setTimeout(applyFilters, 0));
  const requestedCountry = new URLSearchParams(window.location.search).get("country");
  if (requestedCountry) {
    const select = form.querySelector('[data-filter="country"]');
    if (select && Array.from(select.options).some((option) => option.value === requestedCountry)) {
      select.value = requestedCountry;
    }
  }
  applyFilters();
}

function initRecordFilters() {
  document.querySelectorAll("[data-record-filters]").forEach((form) => {
    const list = document.getElementById(form.dataset.list);
    const count = document.getElementById(form.dataset.count);
    const empty = document.querySelector("[data-record-empty]");
    if (!list) return;
    const cards = Array.from(list.querySelectorAll("[data-record]"));
    const queryInput = form.querySelector('[data-filter="query"]');
    const countrySelect = form.querySelector('[data-filter="country"]');

    function applyFilters() {
      const query = (queryInput?.value || "").trim().toLowerCase();
      const country = countrySelect?.value || "";
      let visible = 0;
      for (const card of cards) {
        const text = card.dataset.text || card.textContent.toLowerCase();
        const show = (!query || text.includes(query)) && (!country || card.dataset.country === country);
        card.hidden = !show;
        if (show) visible += 1;
      }
      if (count) count.textContent = `${visible} ${visible === 1 ? "record" : "records"}`;
      if (empty) empty.hidden = visible !== 0;
    }

    form.addEventListener("input", applyFilters);
    form.addEventListener("change", applyFilters);
    form.addEventListener("reset", () => window.setTimeout(applyFilters, 0));
    const requested = new URLSearchParams(window.location.search).get("country");
    if (requested && countrySelect) countrySelect.value = requested;
    applyFilters();
  });
}

function initCountryFilters() {
  document.querySelectorAll("[data-country-filters]").forEach((form) => {
    const cards = Array.from(document.querySelectorAll("[data-country]"));
    if (!cards.length) return;
    const queryInput = form.querySelector('[data-filter="query"]');
    const regionSelect = form.querySelector('[data-filter="region"]');
    const coverageSelect = form.querySelector('[data-filter="coverage"]');
    const count = document.getElementById("country-count");
    const empty = document.querySelector("[data-country-empty]");

    function applyFilters() {
      const query = (queryInput?.value || "").trim().toLowerCase();
      const region = regionSelect?.value || "";
      const coverage = coverageSelect?.value || "";
      let visible = 0;
      for (const card of cards) {
        const text = card.textContent.toLowerCase();
        const show =
          (!query || text.includes(query)) &&
          (!region || card.dataset.region === region) &&
          (!coverage || card.dataset.coverage === coverage);
        card.hidden = !show;
        if (show) visible += 1;
      }
      document.querySelectorAll("[data-country-section]").forEach((section) => {
        section.hidden = !section.querySelector("[data-country]:not([hidden])");
      });
      if (count) count.textContent = `${visible} ${visible === 1 ? "country" : "countries"}`;
      if (empty) empty.hidden = visible !== 0;
    }

    form.addEventListener("input", applyFilters);
    form.addEventListener("change", applyFilters);
    form.addEventListener("reset", () => window.setTimeout(applyFilters, 0));
    applyFilters();
  });
}

function initSourceFilters() {
  const form = document.querySelector("[data-source-filters]");
  const list = document.querySelector("[data-source-list]");
  if (!form || !list) return;
  const cards = Array.from(list.querySelectorAll("[data-source]"));
  const queryInput = form.querySelector('[data-filter="query"]');
  const countrySelect = form.querySelector('[data-filter="country"]');
  const statusSelect = form.querySelector('[data-filter="status"]');
  const count = document.getElementById("source-count");
  const empty = document.querySelector("[data-source-empty]");

  function applyFilters() {
    const query = (queryInput?.value || "").trim().toLowerCase();
    const country = countrySelect?.value || "";
    const status = statusSelect?.value || "";
    let visible = 0;
    for (const card of cards) {
      const show =
        (!query || card.textContent.toLowerCase().includes(query)) &&
        (!country || card.dataset.country === country) &&
        (!status || card.dataset.status === status);
      card.hidden = !show;
      if (show) visible += 1;
    }
    if (count) count.textContent = `${visible} ${visible === 1 ? "source" : "sources"}`;
    if (empty) empty.hidden = visible !== 0;
  }

  form.addEventListener("input", applyFilters);
  form.addEventListener("change", applyFilters);
  form.addEventListener("reset", () => window.setTimeout(applyFilters, 0));
  applyFilters();
}

initSiteSearch();
initTenderFilters();
initRecordFilters();
initCountryFilters();
initSourceFilters();
