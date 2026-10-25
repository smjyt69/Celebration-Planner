/* Reading the event form and showing validation errors next to the inputs. */
import { $ } from "./dom.js";

const FIELD_NAMES = ["event_type", "title", "event_date", "guests", "budget", "currency",
  "venue_type", "vibe", "dietary", "attendees", "interests", "question"];

const toInt = (value) => (value === "" || value === null ? null : Number(value));

/** Collect the form into the payload the API expects. Server-side validation is the authority. */
export function readForm(form) {
  const data = new FormData(form);
  return {
    event_type: data.get("event_type"),
    title: data.get("title") || "",
    event_date: data.get("event_date"),
    guests: toInt(data.get("guests")),
    budget: toInt(data.get("budget")),
    currency: data.get("currency"),
    venue_type: data.get("venue_type"),
    vibe: data.get("vibe"),
    dietary: data.getAll("dietary"),
    attendees: data.getAll("attendees"),
    interests: String(data.get("interests") || "").split(",").map((s) => s.trim()).filter(Boolean),
  };
}

/** Hide every field error and clear aria-invalid. */
export function clearErrors() {
  for (const name of FIELD_NAMES) {
    const message = $(`err-${name}`);
    if (message) {
      message.hidden = true;
      message.textContent = "";
    }
    const input = $(name);
    if (input) input.removeAttribute("aria-invalid");
  }
  $("form-error").hidden = true;
}

/**
 * Show per-field messages and focus the first invalid input. With no field messages,
 * show `fallback` in the general error box instead.
 */
export function showErrors(fields, fallback) {
  let firstInvalid = null;
  for (const [name, text] of Object.entries(fields || {})) {
    const message = $(`err-${name}`);
    if (!message) continue;
    message.textContent = text;
    message.hidden = false;
    const input = $(name);
    if (input) {
      input.setAttribute("aria-invalid", "true");
      firstInvalid = firstInvalid || input;
    }
  }
  if (firstInvalid) {
    firstInvalid.focus();
    return;
  }
  const box = $("form-error");
  box.textContent = fallback || "Something went wrong. Please try again.";
  box.hidden = false;
}
