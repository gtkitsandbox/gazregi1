document.documentElement.classList.add("js");

const pagefindImport = "/pagefind/pagefind.js";
let pagefind;
let latestSearch = 0;

const SEARCH_SCOPES = {
  all: { label: "", paths: null, landing: "/" },
  people: { label: "people", paths: ["/people/"], landing: "/people/" },
  organisations: { label: "organisations", paths: ["/organisations/"], landing: "/organisations/" },
  gazettes: { label: "gazettes", paths: ["/gazettes/", "/records/"], landing: "/gazettes/" },
  tenders: { label: "tenders", paths: ["/tenders/"], landing: "/tenders/" },
};

function initSiteSearch() {
  const form = document.querySelector("#search-form");
  const input = document.querySelector("#search-query");
  const results = document.querySelector("#search-results");
  const count = document.querySelector("#result-count");
  const panel = document.querySelector("#search-results-panel");
  if (!form || !input || !results || !count) return;

  const initialResults = results.innerHTML;
  const initialCount = count.textContent;
  const scopeButtons = Array.from(document.querySelectorAll(".search-scope"));
  let scope = "all";

  function setScope(nextScope) {
    scope = SEARCH_SCOPES[nextScope] ? nextScope : "all";
    for (const button of scopeButtons) {
      const active = button.dataset.scope === scope;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    }
  }

  function matchesScope(url) {
    const paths = SEARCH_SCOPES[scope].paths;
    if (!paths) return true;
    let pathname = url;
    try {
      pathname = new URL(url, window.location.origin).pathname;
    } catch {
      pathname = url;
    }
    return paths.some((path) => pathname.startsWith(path));
  }

  function resultLabel(amount) {
    const category = SEARCH_SCOPES[scope].label;
    const noun = amount === 1 ? "result" : "results";
    return category ? `${amount} ${noun} in ${category}` : `${amount} ${noun}`;
  }

  async function runSearch(query) {
    const requestId = ++latestSearch;
    const trimmed = query.trim();
    if (!trimmed) {
      results.innerHTML = initialResults;
      count.textContent = initialCount;
      if (panel) panel.hidden = true;
      return;
    }

    if (panel) panel.hidden = false;
    count.textContent = "Searching...";
    results.setAttribute("aria-busy", "true");
    try {
      if (!pagefind) pagefind = await import(pagefindImport);
      const response = await pagefind.search(trimmed);
      const matches = (await Promise.all(response.results.map((result) => result.data())))
        .filter((result) => matchesScope(result.url))
        .slice(0, 30);
      if (requestId !== latestSearch) return;

      results.replaceChildren(...matches.map(renderResult));
      count.textContent = `${resultLabel(matches.length)} for “${trimmed}”`;
      if (matches.length === 0) {
        const empty = document.createElement("p");
        empty.className = "empty-state";
        empty.textContent = "No indexed pages match this search in the selected category.";
        results.append(empty);
      }
    } catch {
      count.textContent = "Search index could not be loaded. Try refreshing the page.";
    } finally {
      results.removeAttribute("aria-busy");
    }
  }

  for (const button of scopeButtons) {
    button.addEventListener("click", () => {
      setScope(button.dataset.scope);
      if (input.value.trim()) {
        runSearch(input.value);
      } else {
        count.textContent = scope === "all"
          ? initialCount
          : `Searching ${SEARCH_SCOPES[scope].label}. Enter a term, or submit to browse that category.`;
      }
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const trimmed = input.value.trim();
    if (!trimmed) {
      if (scope !== "all") window.location.href = SEARCH_SCOPES[scope].landing;
      return;
    }
    runSearch(trimmed);
    if (panel) {
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      panel.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    }
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
      const matchesKind = !values.kind || card.dataset.kind === values.kind;
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
        matchesQuery && matchesKind && matchesSector && matchesLocation && matchesOrganisation && matchesCountry && matchesClosing;
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

function initSearchShortcut() {
  document.addEventListener("keydown", (event) => {
    const active = document.activeElement;
    const isInput =
      active &&
      (active.tagName === "INPUT" ||
        active.tagName === "TEXTAREA" ||
        active.tagName === "SELECT" ||
        active.isContentEditable);
    const isSlash = event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey;
    const isCommandK = event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey);
    if ((!isSlash && !isCommandK) || (isSlash && isInput)) return;

    const target = document.querySelector("#search-query") || document.querySelector("#global-search");
    if (!target) return;
    event.preventDefault();
    target.focus();
    target.select();
  });
}

function initReveal() {
  const targets = Array.from(document.querySelectorAll("[data-reveal]"));
  if (!targets.length) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced || typeof IntersectionObserver === "undefined") {
    targets.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  const thresholdY = window.innerHeight * 0.98;
  const pending = [];
  for (const el of targets) {
    if (el.getBoundingClientRect().top < thresholdY) {
      el.classList.add("is-visible");
    } else {
      el.classList.add("is-animated");
      pending.push(el);
    }
  }
  if (!pending.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    },
    { threshold: 0.05, rootMargin: "0px 0px -20px 0px" },
  );

  for (const el of pending) {
    observer.observe(el);
  }
}

function initQuickQueries() {
  const buttons = document.querySelectorAll("[data-quick-query]");
  const form = document.querySelector("#search-form");
  const input = document.querySelector("#search-query");
  if (!buttons.length || !form || !input) return;

  for (const button of buttons) {
    button.addEventListener("click", () => {
      const q = button.dataset.quickQuery || "";
      input.value = q;
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
      }
    });
  }
}

initSiteSearch();
initTenderFilters();
initRecordFilters();
initCountryFilters();
initSourceFilters();
initSearchShortcut();
initReveal();
initQuickQueries();
