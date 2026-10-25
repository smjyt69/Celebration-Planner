/* Checklist state: ticked items are remembered in this browser (localStorage, best effort). */
import { $, el } from "./dom.js";

export class Checklist {
  #key = "";
  #total = 0;
  #ticked = {};

  /** Begin a new plan: remember which items were ticked before for this key. */
  start(key, total) {
    this.#key = key;
    this.#total = total;
    this.#ticked = this.#load();
  }

  /** Create a labelled checkbox that saves its state and refreshes the progress bar. */
  checkbox(id, text) {
    const input = el("input", { type: "checkbox", id });
    input.checked = Boolean(this.#ticked[id]);
    input.addEventListener("change", () => {
      if (input.checked) this.#ticked[id] = true;
      else delete this.#ticked[id];
      this.#save();
      this.updateProgress();
    });
    return { input, label: el("label", { for: id, text }) };
  }

  /** Recount ticked boxes and update the progress element and its text. */
  updateProgress() {
    const done = document.querySelectorAll("#results .checklist input:checked, #vendors input:checked").length;
    $("progress").max = Math.max(this.#total, 1);
    $("progress").value = done;
    $("progress-text").textContent = `${done} of ${this.#total} done`;
  }

  #load() {
    try {
      return JSON.parse(localStorage.getItem(this.#key) || "{}");
    } catch (_) {
      return {}; // storage blocked or corrupted: start fresh
    }
  }

  #save() {
    try {
      localStorage.setItem(this.#key, JSON.stringify(this.#ticked));
    } catch (_) {
      /* storage unavailable: the page still works, progress just is not remembered */
    }
  }
}
