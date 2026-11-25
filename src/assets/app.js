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
  const scopeSelect = document.querySelector("#hero-scope-select");
  const countrySelect = document.querySelector("#hero-country-select");
  let scope = "all";

  function setScope(nextScope) {
    scope = SEARCH_SCOPES[nextScope] ? nextScope : "all";
    for (const button of scopeButtons) {
      const active = button.dataset.scope === scope;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    }
    if (scopeSelect && scopeSelect.value !== scope) {
      scopeSelect.value = scope;
    }
  }

  function effectiveQuery(rawQuery) {
    const trimmed = (rawQuery || "").trim();
    const countryName = countrySelect?.selectedOptions?.[0]?.dataset?.countryName || "";
    if (!trimmed) return countryName;
    return countryName && !trimmed.toLowerCase().includes(countryName.toLowerCase())
      ? `${trimmed} ${countryName}`
      : trimmed;
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
      const combined = effectiveQuery(input.value);
      if (combined) {
        runSearch(combined);
      } else {
        count.textContent = scope === "all"
          ? initialCount
          : `Searching ${SEARCH_SCOPES[scope].label}. Enter a term, or submit to browse that category.`;
      }
    });
  }

  if (scopeSelect) {
    scopeSelect.addEventListener("change", () => {
      setScope(scopeSelect.value);
      const combined = effectiveQuery(input.value);
      if (combined) {
        runSearch(combined);
      }
    });
  }

  if (countrySelect) {
    countrySelect.addEventListener("change", () => {
      const combined = effectiveQuery(input.value);
      if (combined) {
        runSearch(combined);
      } else {
        count.textContent = initialCount;
        if (panel) panel.hidden = true;
      }
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const raw = input.value.trim();
    const countryCode = countrySelect?.value || "";
    if (!raw && countryCode && scope === "tenders") {
      window.location.href = `/tenders/?country=${encodeURIComponent(countryCode)}`;
      return;
    }
    const combined = effectiveQuery(raw);
    if (!combined) {
      if (scope !== "all") window.location.href = SEARCH_SCOPES[scope].landing;
      return;
    }
    runSearch(combined);
    if (panel) {
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      panel.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    }
  });

  input.addEventListener("input", () => {
    window.clearTimeout(input.searchTimer);
    input.searchTimer = window.setTimeout(() => runSearch(effectiveQuery(input.value)), 160);
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
  const sortSelect = document.querySelector("#tender-sort");
  const chipsContainer = document.querySelector("#tender-active-chips");
  const exportBtn = document.querySelector("#tender-export-csv");
  const viewButtons = Array.from(document.querySelectorAll("[data-view-toggle]"));

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

  function setView(mode) {
    const isTable = mode === "table";
    list.classList.toggle("tender-list--table", isTable);
    for (const btn of viewButtons) {
      const active = btn.dataset.viewToggle === mode;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    }
    try {
      window.localStorage.setItem("gazregi_tender_view", mode);
    } catch {
      // Ignore storage failures
    }
  }

  if (viewButtons.length) {
    let savedView = "cards";
    try {
      savedView = window.localStorage.getItem("gazregi_tender_view") || "cards";
    } catch {
      savedView = "cards";
    }
    setView(savedView === "table" ? "table" : "cards");
    for (const btn of viewButtons) {
      btn.addEventListener("click", () => setView(btn.dataset.viewToggle || "cards"));
    }
  }

  function renderActiveChips() {
    if (!chipsContainer) return;
    const chips = [];
    if (queryInput && queryInput.value.trim()) {
      chips.push({
        label: `Search: “${queryInput.value.trim()}”`,
        clear: () => { queryInput.value = ""; },
      });
    }
    for (const select of selects) {
      if (!select.value) continue;
      const optionText = select.selectedOptions?.[0]?.textContent || select.value;
      const fieldLabel = form.querySelector(`label[for="${select.id}"]`)?.textContent || select.dataset.filter;
      chips.push({
        label: `${fieldLabel}: ${optionText}`,
        clear: () => { select.value = ""; },
      });
    }
    chipsContainer.replaceChildren();
    if (!chips.length) {
      chipsContainer.hidden = true;
      return;
    }
    chipsContainer.hidden = false;
    for (const chip of chips) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "active-chip";
      btn.textContent = `${chip.label} ×`;
      btn.setAttribute("aria-label", `Remove filter ${chip.label}`);
      btn.addEventListener("click", () => {
        chip.clear();
        applyFilters();
      });
      chipsContainer.append(btn);
    }
  }

  function applySort() {
    if (!sortSelect) return;
    const mode = sortSelect.value || "default";
    const sorted = [...cards].sort((a, b) => {
      if (mode === "title") {
        return (a.dataset.title || "").localeCompare(b.dataset.title || "");
      }
      if (mode === "country") {
        return (a.dataset.countryName || "").localeCompare(b.dataset.countryName || "") ||
          Number(a.dataset.order || 0) - Number(b.dataset.order || 0);
      }
      return Number(a.dataset.order || 0) - Number(b.dataset.order || 0);
    });
    for (const card of sorted) list.append(card);
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
    renderActiveChips();
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      const visibleCards = Array.from(list.querySelectorAll("[data-tender]:not([hidden])"));
      const escapeCsv = (val) => `"${String(val || "").replace(/"/g, '""')}"`;
      const header = ["Reference", "Title", "Country", "Issuer", "Sector", "Status", "Closing", "URL"];
      const rows = visibleCards.map((c) => [
        c.dataset.reference,
        c.dataset.title,
        c.dataset.countryName,
        c.dataset.issuer,
        c.dataset.sector,
        c.dataset.status,
        c.dataset.closingLabel || c.dataset.closing,
        new URL(c.dataset.url || "", window.location.origin).href,
      ].map(escapeCsv).join(","));
      const csv = [header.join(","), ...rows].join("\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "gazetteregistry-tenders.csv";
      document.body.append(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  }

  form.addEventListener("input", applyFilters);
  form.addEventListener("change", applyFilters);
  form.addEventListener("reset", () => window.setTimeout(applyFilters, 0));
  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      applySort();
      applyFilters();
    });
  }

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
    if (!isSlash || isInput) return;

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

function initCopyButtons() {
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-copy]");
    if (!btn) return;
    const text = btn.dataset.copy;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      try {
        document.execCommand("copy");
      } catch {
        // Ignore fallback failure
      }
      area.remove();
    }
    btn.classList.add("is-copied");
    const span = btn.querySelector("span");
    const origText = span ? span.textContent : null;
    if (span && origText) span.textContent = "Copied";
    window.setTimeout(() => {
      btn.classList.remove("is-copied");
      if (span && origText) span.textContent = origText;
    }, 1500);
  });
}

function initCommandPalette() {
  const dialog = document.querySelector("#cmd-palette");
  const cmdInput = document.querySelector("#cmd-input");
  const cmdResults = document.querySelector("#cmd-results");
  if (!dialog || !cmdInput || !cmdResults) return;

  let cmdSearchId = 0;
  function openCmd() {
    if (!dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    cmdInput.focus();
    cmdInput.select();
  }
  function closeCmd() {
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  document.querySelectorAll("[data-open-cmd]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      openCmd();
    });
  });
  document.querySelectorAll("[data-close-cmd]").forEach((btn) => {
    btn.addEventListener("click", closeCmd);
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeCmd();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      if (dialog.open) closeCmd();
      else openCmd();
    }
  });

  cmdInput.addEventListener("input", () => {
    window.clearTimeout(cmdInput.cmdTimer);
    cmdInput.cmdTimer = window.setTimeout(async () => {
      const q = cmdInput.value.trim();
      const myId = ++cmdSearchId;
      if (!q) {
        cmdResults.innerHTML = '<p class="cmd-dialog__empty">Search across all indexed official documents instantly via Pagefind.</p>';
        return;
      }
      cmdResults.innerHTML = '<p class="cmd-dialog__empty">Searching…</p>';
      try {
        if (!pagefind) pagefind = await import(pagefindImport);
        const res = await pagefind.search(q);
        const matches = await Promise.all(res.results.slice(0, 12).map((r) => r.data()));
        if (myId !== cmdSearchId) return;
        if (!matches.length) {
          cmdResults.innerHTML = '<p class="cmd-dialog__empty">No indexed records match that query.</p>';
          return;
        }
        const nodes = matches.map((m) => {
          const a = document.createElement("a");
          a.className = "cmd-result";
          a.href = m.url;
          const t = document.createElement("strong");
          t.textContent = m.meta?.title?.replace(/\s*\|\s*GazetteRegistry\s*$/, "") || m.url;
          const p = document.createElement("span");
          p.innerHTML = m.excerpt;
          a.append(t, p);
          return a;
        });
        cmdResults.replaceChildren(...nodes);
      } catch {
        cmdResults.innerHTML = '<p class="cmd-dialog__empty">Search index unavailable right now.</p>';
      }
    }, 140);
  });
}

initSiteSearch();
initTenderFilters();
initRecordFilters();
initCountryFilters();
initSourceFilters();
initSearchShortcut();
initReveal();
initQuickQueries();
initCopyButtons();
initCommandPalette();
