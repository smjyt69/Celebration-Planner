/* Celebration Planner front end.
 * All dynamic content is inserted with textContent / createElement (never as HTML strings),
 * so server or user text cannot inject markup. Loaded as an external script to satisfy the CSP. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const form = $("plan-form");
  const askForm = $("ask-form");
  const FIELD_NAMES = ["event_type", "title", "event_date", "guests", "budget", "currency",
    "venue_type", "vibe", "dietary", "attendees", "interests", "question"];

  let currentPayload = null;
  let storeKey = "";
  let totalItems = 0;

  // ---------- helpers
  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (key === "text") node.textContent = value;
      else if (key === "class") node.className = value;
      else node.setAttribute(key, value);
    }
    for (const child of children) node.append(child);
    return node;
  }

  function money(amount, plan) {
    try {
      const locale = plan.summary.currency === "INR" ? "en-IN" : undefined;
      return new Intl.NumberFormat(locale, { style: "currency", currency: plan.summary.currency, maximumFractionDigits: 0 }).format(amount);
    } catch (_) {
      return plan.summary.symbol + amount.toLocaleString();
    }
  }

  function formatDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  function toInt(value) {
    return value === "" || value === null ? null : Number(value);
  }

  function setStatus(message) { $("status").textContent = message; }

  function clearErrors() {
    for (const name of FIELD_NAMES) {
      const err = $("err-" + name);
      if (err) { err.hidden = true; err.textContent = ""; }
      const input = document.getElementById(name);
      if (input) input.removeAttribute("aria-invalid");
    }
    $("form-error").hidden = true;
  }

  function showErrors(fields, message) {
    let first = null;
    for (const [name, text] of Object.entries(fields || {})) {
      const err = $("err-" + name);
      if (!err) continue;
      err.textContent = text;
      err.hidden = false;
      const input = document.getElementById(name);
      if (input) { input.setAttribute("aria-invalid", "true"); first = first || input; }
    }
    if (!first) {
      const box = $("form-error");
      box.textContent = message || "Something went wrong. Please try again.";
      box.hidden = false;
    } else {
      first.focus();
    }
  }

  async function post(path, body) {
    const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    let data = null;
    try { data = await res.json(); } catch (_) { /* non-JSON error body */ }
    if (!res.ok) {
      const err = new Error((data && data.error) || "Request failed (" + res.status + ").");
      err.fields = (data && data.fields) || {};
      throw err;
    }
    return data;
  }

  function readForm() {
    const fd = new FormData(form);
    return {
      event_type: fd.get("event_type"),
      title: fd.get("title") || "",
      event_date: fd.get("event_date"),
      guests: toInt(fd.get("guests")),
      budget: toInt(fd.get("budget")),
      currency: fd.get("currency"),
      venue_type: fd.get("venue_type"),
      vibe: fd.get("vibe"),
      dietary: fd.getAll("dietary"),
      attendees: fd.getAll("attendees"),
      interests: String(fd.get("interests") || "").split(",").map((s) => s.trim()).filter(Boolean),
    };
  }

  // ---------- saved checklist state (best effort: storage may be blocked)
  function loadChecked() {
    try { return JSON.parse(localStorage.getItem(storeKey) || "{}"); } catch (_) { return {}; }
  }
  function saveChecked(state) {
    try { localStorage.setItem(storeKey, JSON.stringify(state)); } catch (_) { /* ignore */ }
  }
  function updateProgress() {
    const done = document.querySelectorAll("#results .checklist input:checked, #vendors input:checked").length;
    $("progress").max = Math.max(totalItems, 1);
    $("progress").value = done;
    $("progress-text").textContent = done + " of " + totalItems + " done";
  }
  function checkbox(id, text, state) {
    const input = el("input", { type: "checkbox", id: id });
    input.checked = Boolean(state[id]);
    input.addEventListener("change", () => {
      const s = loadChecked();
      if (input.checked) s[id] = true; else delete s[id];
      saveChecked(s);
      updateProgress();
    });
    return { input, label: el("label", { for: id, text: text }) };
  }

  // ---------- renderers
  function renderNotes(plan) {
    const list = $("notes");
    list.replaceChildren(...plan.notes.map((n) => el("li", { class: n.level, text: (n.level === "warning" ? "Heads up: " : "Tip: ") + n.text })));
  }

  function renderBudget(plan) {
    const s = plan.summary, b = plan.budget;
    $("budget-summary").textContent = "About " + money(b.per_guest, plan) + " per guest for " + s.guests.toLocaleString() + " guests.";
    const rows = b.lines.map((line) => {
      const bar = el("span", { class: "bar", "aria-hidden": "true" });
      bar.style.width = Math.max(line.percent * 3, 2) + "px";
      return el("tr", {},
        el("th", { scope: "row", text: line.label }),
        el("td", {}, bar, document.createTextNode(line.percent + "%")),
        el("td", { class: "num", text: money(line.amount, plan) }));
    });
    document.querySelector("#budget-table tbody").replaceChildren(...rows);
  }

  function renderTimeline(plan, state) {
    const items = plan.timeline.tasks.map((t) => {
      const due = el("span", { class: "due", text: "Due " + formatDate(t.due_date) + (t.days_before === 0 ? " (event day)" : " (" + t.days_before + " days before)") });
      const { input, label } = checkbox("task-" + t.id, t.title, state);
      if (t.critical) label.append(el("span", { class: "badge", text: "Key task" }));
      label.append(due);
      return el("li", {}, input, label);
    });
    $("timeline").replaceChildren(...items);
  }

  function renderVendors(plan, state) {
    const blocks = plan.vendors.map((v) => {
      const group = (title, list, prefix) => {
        const ul = el("ul", { class: "checklist" });
        list.forEach((text, i) => {
          const { input, label } = checkbox("v-" + v.category + "-" + prefix + i, text, state);
          ul.append(el("li", {}, input, label));
        });
        return [el("h4", { text: title }), ul];
      };
      const budget = v.budget === null || v.budget === undefined ? "" : " (budget " + money(v.budget, plan) + ")";
      return el("details", {},
        el("summary", { text: v.vendor + budget }),
        el("div", {}, ...group("Questions to ask", v.ask, "a"), ...group("Put in the contract", v.contract, "c")));
    });
    $("vendors").replaceChildren(...blocks);
  }

  function renderIdeas(plan) {
    $("ideas").replaceChildren(...plan.ideas.map((text) => el("li", { text })));
  }

  function renderPlan(plan) {
    const s = plan.summary;
    storeKey = "cp:" + [s.event_type, s.event_date, s.title].join("|");
    const state = loadChecked();
    totalItems = plan.timeline.tasks.length + plan.vendors.reduce((n, v) => n + v.ask.length + v.contract.length, 0);
    $("summary").textContent = s.title + " on " + formatDate(s.event_date) + " (" + s.days_left + " days away), " +
      s.guests.toLocaleString() + " guests, budget " + money(s.budget, plan) + ".";
    renderNotes(plan); renderBudget(plan); renderTimeline(plan, state); renderVendors(plan, state); renderIdeas(plan);
    $("ai-ideas").replaceChildren(); $("answer").replaceChildren();
    updateProgress();
    const results = $("results");
    results.hidden = false;
    results.focus();
  }

  // ---------- events
  async function withBusy(button, busyText, fn) {
    const original = button.textContent;
    button.disabled = true; button.textContent = busyText; button.setAttribute("aria-busy", "true");
    try { return await fn(); } finally {
      button.disabled = false; button.textContent = original; button.removeAttribute("aria-busy");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();
    currentPayload = readForm();
    try {
      const plan = await withBusy($("submit-btn"), "Building your plan...", () => post("/api/plan", currentPayload));
      setStatus("Your plan is ready.");
      renderPlan(plan);
    } catch (err) {
      setStatus("");
      showErrors(err.fields, err.message);
    }
  });

  $("ai-ideas-btn").addEventListener("click", async () => {
    if (!currentPayload) return;
    const box = $("ai-ideas");
    try {
      const data = await withBusy($("ai-ideas-btn"), "Thinking...", () => post("/api/ideas", currentPayload));
      if (data.ai_used) {
        box.replaceChildren(el("h4", { text: "From the AI assistant" }), el("ul", {}, ...data.ai_ideas.map((t) => el("li", { text: t }))));
      } else {
        box.replaceChildren(el("p", { class: "hint", text: "The AI assistant is not available right now, so the built-in ideas above are what you get." }));
      }
    } catch (err) {
      box.replaceChildren(el("p", { class: "error", text: err.message }));
    }
  });

  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();
    if (!currentPayload) return;
    const question = $("question").value;
    try {
      const data = await withBusy($("ask-btn"), "Thinking...", () => post("/api/ask", Object.assign({}, currentPayload, { question })));
      $("answer").replaceChildren(document.createTextNode(data.answer),
        el("span", { class: "source", text: data.source === "ai" ? "Answered by the AI assistant" : "Answered by the built-in planner" }));
    } catch (err) {
      if (err.fields && err.fields.question) showErrors({ question: err.fields.question });
      else $("answer").replaceChildren(el("p", { class: "error", text: err.message }));
    }
  });

  $("print-btn").addEventListener("click", () => window.print());

  // Stop the date picker offering past dates (the server re-validates).
  const today = new Date();
  const iso = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  $("event_date").min = iso(today);
})();
