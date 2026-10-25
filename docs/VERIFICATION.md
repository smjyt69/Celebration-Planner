# Verification

How to check this project yourself, and the output of the checks as they were last run.
Nothing here is a score or a claim: re-run the commands to confirm.

Last run: 2026-10-25, Python 3.13.16, headless Chromium (Playwright).

## 1. Unit and API tests

```bash
python -m unittest discover -s tests -t .      # standard library only; pytest also works
```

```text
Ran 106 tests in 0.093s
OK
```

Tests per file:

```text
tests/test_api.py        21
tests/test_config.py     8
tests/test_content.py    11
tests/test_engine.py     28
tests/test_llm.py        12
tests/test_ratelimit.py  5
tests/test_validation.py 21
```

What they cover: budget invariants across every event / venue / affordability combination, timeline
compression, vendor filtering, field-by-field validation, content-file validation, settings, the
rate limiter, API status codes, security headers, path traversal, prompt-injection escaping, and
AI-failure fallback.

## 2. Real-browser check

```bash
pip install playwright && playwright install chromium
python scripts/browser_check.py
```

```text
PASS  empty submit shows field errors
  PASS  results stay hidden after invalid submit
  PASS  focus moves to the first invalid field
  PASS  focus moves to the results
  PASS  event name is shown as literal text
  PASS  no HTML injected from user input
  PASS  budget table rendered
  PASS  timeline rendered
  PASS  vendor checklist rendered
  PASS  context notes shown
  PASS  progress updates
  PASS  ticked task is remembered after reload
  PASS  vendor details open
  PASS  question answered
  PASS  AI ideas fall back gracefully without a key
  PASS  skip link is the first tab stop
  PASS  skip link jumps to main content
  PASS  no horizontal scroll at 360px wide
  PASS  no unexpected console errors or CSP violations
All browser checks passed.
```

The check also fails on any browser console error, which includes Content-Security-Policy violations.

## 3. Lint and type checks

```bash
pip install -r requirements-dev.txt
ruff check .          # rules: E, F, W, I, B, S   (config in pyproject.toml)
mypy                  # config in pyproject.toml
```

These run in GitHub Actions on every push (`.github/workflows/ci.yml`): the test job blocks, the lint job is
advisory. See the Actions tab for the current result; this file does not record it because it changes with every commit.

## 4. Manual checks worth doing

- Keyboard only: Tab through the page, open a vendor, tick items, submit with Enter.
- Screen reader: errors are announced; results move focus to the plan heading.
- Print preview: the plan prints without forms and buttons.
- `GET /healthz` returns `{"status": "ok"}`.
