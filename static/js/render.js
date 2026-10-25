/* Turns a plan returned by the API into DOM. */
import { $, el } from "./dom.js";
import { formatDate, money } from "./format.js";

const BAR_PIXELS_PER_PERCENT = 3;

function renderNotes(plan) {
  const items = plan.notes.map((note) =>
    el("li", { class: note.level, text: (note.level === "warning" ? "Heads up: " : "Tip: ") + note.text }));
  $("notes").replaceChildren(...items);
}

function renderBudget(plan) {
  const { summary, budget } = plan;
  $("budget-summary").textContent =
    `About ${money(budget.per_guest, plan)} per guest for ${summary.guests.toLocaleString()} guests.`;
  const rows = budget.lines.map((line) => {
    const bar = el("span", { class: "bar", "aria-hidden": "true" });
    bar.style.width = `${Math.max(line.percent * BAR_PIXELS_PER_PERCENT, 2)}px`;
    return el("tr", {},
      el("th", { scope: "row", text: line.label }),
      el("td", {}, bar, document.createTextNode(`${line.percent}%`)),
      el("td", { class: "num", text: money(line.amount, plan) }));
  });
  document.querySelector("#budget-table tbody").replaceChildren(...rows);
}

function renderTimeline(plan, checklist) {
  const items = plan.timeline.tasks.map((task) => {
    const when = task.days_before === 0 ? " (event day)" : ` (${task.days_before} days before)`;
    const { input, label } = checklist.checkbox(`task-${task.id}`, task.title);
    if (task.critical) label.append(el("span", { class: "badge", text: "Key task" }));
    label.append(el("span", { class: "due", text: `Due ${formatDate(task.due_date)}${when}` }));
    return el("li", {}, input, label);
  });
  $("timeline").replaceChildren(...items);
}

function checklistGroup(title, entries, idPrefix, checklist) {
  const list = el("ul", { class: "checklist" });
  entries.forEach((text, index) => {
    const { input, label } = checklist.checkbox(`${idPrefix}${index}`, text);
    list.append(el("li", {}, input, label));
  });
  return [el("h4", { text: title }), list];
}

function renderVendors(plan, checklist) {
  const blocks = plan.vendors.map((vendor) => {
    const budget = vendor.budget == null ? "" : ` (budget ${money(vendor.budget, plan)})`;
    return el("details", {},
      el("summary", { text: vendor.vendor + budget }),
      el("div", {},
        ...checklistGroup("Questions to ask", vendor.ask, `v-${vendor.category}-a`, checklist),
        ...checklistGroup("Put in the contract", vendor.contract, `v-${vendor.category}-c`, checklist)));
  });
  $("vendors").replaceChildren(...blocks);
}

function renderIdeas(plan) {
  $("ideas").replaceChildren(...plan.ideas.map((text) => el("li", { text })));
}

/** Total tickable items: timeline tasks plus every vendor question and contract point. */
function countItems(plan) {
  return plan.timeline.tasks.length + plan.vendors.reduce((n, v) => n + v.ask.length + v.contract.length, 0);
}

/** Render the whole plan, restore saved ticks, show the results region and move focus to it. */
export function renderPlan(plan, checklist) {
  const { summary } = plan;
  checklist.start(`cp:${[summary.event_type, summary.event_date, summary.title].join("|")}`, countItems(plan));
  $("summary").textContent =
    `${summary.title} on ${formatDate(summary.event_date)} (${summary.days_left} days away), ` +
    `${summary.guests.toLocaleString()} guests, budget ${money(summary.budget, plan)}.`;
  renderNotes(plan);
  renderBudget(plan);
  renderTimeline(plan, checklist);
  renderVendors(plan, checklist);
  renderIdeas(plan);
  $("ai-ideas").replaceChildren();
  $("answer").replaceChildren();
  checklist.updateProgress();
  const results = $("results");
  results.hidden = false;
  results.focus();
}
