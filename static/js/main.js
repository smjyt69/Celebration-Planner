/* Entry point: wires the forms and buttons to the API and the renderers. */
import { post } from "./api.js";
import { Checklist } from "./checklist.js";
import { $, el, setStatus, withBusy } from "./dom.js";
import { clearErrors, readForm, showErrors } from "./form.js";
import { toIsoDate } from "./format.js";
import { renderPlan } from "./render.js";

const checklist = new Checklist();
let currentPayload = null; // the last form the user submitted successfully-or-not; reused by ideas and questions

async function onCreatePlan(event) {
  event.preventDefault();
  clearErrors();
  currentPayload = readForm($("plan-form"));
  try {
    const plan = await withBusy($("submit-btn"), "Building your plan...", () => post("/api/plan", currentPayload));
    setStatus("Your plan is ready.");
    renderPlan(plan, checklist);
  } catch (error) {
    setStatus("");
    showErrors(error.fields, error.message);
  }
}

async function onAiIdeas() {
  if (!currentPayload) return;
  const box = $("ai-ideas");
  try {
    const data = await withBusy($("ai-ideas-btn"), "Thinking...", () => post("/api/ideas", currentPayload));
    if (data.ai_used) {
      box.replaceChildren(el("h4", { text: "From the AI assistant" }),
        el("ul", {}, ...data.ai_ideas.map((text) => el("li", { text }))));
    } else {
      box.replaceChildren(el("p", {
        class: "hint",
        text: "The AI assistant is not available right now, so the built-in ideas above are what you get.",
      }));
    }
  } catch (error) {
    box.replaceChildren(el("p", { class: "error", text: error.message }));
  }
}

async function onAsk(event) {
  event.preventDefault();
  clearErrors();
  if (!currentPayload) return;
  const body = { ...currentPayload, question: $("question").value };
  try {
    const data = await withBusy($("ask-btn"), "Thinking...", () => post("/api/ask", body));
    const source = data.source === "ai" ? "Answered by the AI assistant" : "Answered by the built-in planner";
    $("answer").replaceChildren(document.createTextNode(data.answer), el("span", { class: "source", text: source }));
  } catch (error) {
    if (error.fields && error.fields.question) showErrors({ question: error.fields.question });
    else $("answer").replaceChildren(el("p", { class: "error", text: error.message }));
  }
}

$("plan-form").addEventListener("submit", onCreatePlan);
$("ai-ideas-btn").addEventListener("click", onAiIdeas);
$("ask-form").addEventListener("submit", onAsk);
$("print-btn").addEventListener("click", () => window.print());
$("event_date").min = toIsoDate(new Date()); // stop the picker offering past dates (the server re-validates)
