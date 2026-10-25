/* DOM helpers shared by every module.
 * Content is only ever inserted with textContent / createElement (never as HTML strings),
 * so server or user text cannot inject markup. */

/** Shorthand for document.getElementById. */
export const $ = (id) => document.getElementById(id);

/**
 * Create an element. `props.text` sets textContent, `props.class` the class name,
 * anything else becomes an attribute. Children are appended in order.
 */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "text") node.textContent = value;
    else if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

/** Update the polite live region that announces progress to screen readers. */
export function setStatus(message) {
  $("status").textContent = message;
}

/** Disable a button and show `busyText` while `task` runs; always restores the button. */
export async function withBusy(button, busyText, task) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  button.setAttribute("aria-busy", "true");
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.textContent = original;
    button.removeAttribute("aria-busy");
  }
}
