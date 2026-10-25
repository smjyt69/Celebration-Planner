"""Optional end-to-end check in a real browser (headless Chromium via Playwright).

Starts the app on a free port, then drives the UI the way a person would and fails loudly if
anything is wrong: field errors, focus management, rendered plan, text-only rendering of user
input, checklist persistence, the question box, keyboard skip link, mobile overflow, and browser
console errors (including Content-Security-Policy violations).

    pip install playwright && playwright install chromium
    python scripts/browser_check.py            # set CHROMIUM_PATH to use an existing browser

Not part of the unit tests because it needs a browser; the unit tests cover the same rules at API level.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import Page, sync_playwright
except ImportError:
    sys.exit("Playwright is not installed: pip install playwright && playwright install chromium")

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_CONSOLE_ERRORS = ("status of 400",)  # the deliberate empty-form submit below


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until_up(port: int) -> None:
    for _ in range(50):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("server did not start")


def fill_wedding_form(page: Page) -> None:
    page.select_option("#event_type", "wedding")
    page.fill("#title", "Asha & Ravi <b>x</b>")
    page.fill("#event_date", "2027-12-10")
    page.fill("#guests", "400")
    page.fill("#budget", "150000")


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{(' - ' + detail) if detail and not condition else ''}")
    if not condition:
        raise AssertionError(name)


def run(url: str, chromium_path: str | None) -> list[str]:
    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium_path) if chromium_path \
            else playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.on("console", lambda m: m.type in ("error", "warning") and console_errors.append(m.text))
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))

        page.goto(url)
        page.click("#submit-btn")
        page.wait_for_selector("#err-budget:not([hidden])")
        check("empty submit shows field errors", page.get_attribute("#budget", "aria-invalid") == "true")
        check("results stay hidden after invalid submit", page.locator("#results").is_hidden())
        check("focus moves to the first invalid field",
              page.evaluate("document.activeElement.id") in ("event_date", "guests", "budget"))

        fill_wedding_form(page)
        page.select_option("#venue_type", "outdoor")
        page.check("input[name=dietary][value=vegetarian]")
        page.check("input[name=attendees][value=seniors]")
        page.fill("#interests", "music, cricket")
        page.click("#submit-btn")
        page.wait_for_selector("#results:not([hidden])")
        check("focus moves to the results", page.evaluate("document.activeElement.id") == "results")
        check("event name is shown as literal text", "Asha & Ravi <b>x</b>" in page.inner_text("#summary"))
        check("no HTML injected from user input", page.locator("#summary b").count() == 0)
        check("budget table rendered", page.locator("#budget-table tbody tr").count() >= 8)
        check("timeline rendered", page.locator("#timeline li").count() >= 10)
        check("vendor checklist rendered", page.locator("#vendors details").count() >= 8)
        notes = page.inner_text("#notes")
        check("context notes shown", "per guest" in notes and "Peak wedding season" in notes, notes)

        page.locator("#timeline input[type=checkbox]").first.check()
        check("progress updates", page.inner_text("#progress-text").startswith("1 of"))
        page.reload()
        fill_wedding_form(page)
        page.click("#submit-btn")
        page.wait_for_selector("#results:not([hidden])")
        first_task = page.locator("#timeline input[type=checkbox]").first
        check("ticked task is remembered after reload", first_task.is_checked())

        page.locator("#vendors summary").first.click()
        check("vendor details open", page.locator("#vendors details[open] li").count() >= 3)
        page.fill("#question", "How is my budget split?")
        page.click("#ask-btn")
        page.wait_for_selector("#answer .source")
        check("question answered", "per guest" in page.inner_text("#answer"))
        page.click("#ai-ideas-btn")
        page.wait_for_selector("#ai-ideas p")
        check("AI ideas fall back gracefully without a key", "not available" in page.inner_text("#ai-ideas"))

        page.goto(url)
        page.keyboard.press("Tab")
        check("skip link is the first tab stop", page.evaluate("document.activeElement.className") == "skip-link")
        page.keyboard.press("Enter")
        check("skip link jumps to main content", page.evaluate("location.hash") == "#main")

        page.set_viewport_size({"width": 360, "height": 800})
        page.goto(url)
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("no horizontal scroll at 360px wide", overflow <= 0, f"{overflow}px overflow")
        browser.close()
    return [m for m in console_errors if not any(expected in m for expected in EXPECTED_CONSOLE_ERRORS)]


def main() -> int:
    port = free_port()
    server = subprocess.Popen([sys.executable, "wsgi.py"], cwd=ROOT, env={**os.environ, "PORT": str(port)},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_until_up(port)
        unexpected = run(f"http://127.0.0.1:{port}/", os.environ.get("CHROMIUM_PATH"))
    finally:
        server.terminate()
        server.wait(timeout=10)
    check("no unexpected console errors or CSP violations", not unexpected, "; ".join(unexpected))
    print("All browser checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
