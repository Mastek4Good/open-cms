# ADR-011: Automated Accessibility Scanning

## Status

Accepted

## Date

2026-11-05

## Context

The app is used by outreach workers, often on phones in the field, and by staff with a range of needs. Accessibility is both a legal expectation for a charity (the Equality Act 2010, and WCAG 2.2 AA as the usual standard) and a practical one. Until now nothing checked it, and a first scan found real problems: the brand blue and several greys failed the 4.5:1 text-contrast ratio, and links inside running text were indistinguishable without colour.

Most of the app is behind a login (with mandatory MFA for admins), so a scanner that only fetches public URLs sees very little.

Options considered:

1. **Lighthouse CI only** — popular and gives a score, but it audits one URL at a time with no built-in sign-in, so authenticated pages need custom scripting. Its accessibility category is axe-core underneath.
2. **pa11y / pa11y-ci** — good CLI, but adds a Node toolchain to a Python project and still needs login scripting.
3. **axe-core driven by Playwright (Python)** — runs inside the existing pytest/uv toolchain, can sign in through the real UI (the shared demo account accepts any MFA code), and can scan any page state.
4. **Manual audits only** — needed anyway, but not repeatable on every change.

## Decision

- **axe-core via Playwright is the blocking gate.** `tests_a11y/` starts the app on a throwaway SQLite database, signs in as the demo account and scans the main public and signed-in pages against WCAG 2.0/2.1/2.2 A and AA. Any violation fails the build.
- **Lighthouse is report-only.** A separate CI job runs its accessibility category on the public pages and uploads the HTML reports. It is non-blocking because it uses the same engine and cannot sign in, so it adds a familiar score and report rather than extra coverage.
- The scan lives in `tests_a11y/`, outside the default `testpaths`, with its dependencies in an `a11y` uv dependency group, so everyday `pytest` stays fast and browser-free.
- The first scan's findings were fixed rather than baselined: the brand scale was darkened one step (`brand-600` to `#0369a1`, with `700`/`800` shifted to match), light grey text on white was moved from `gray-400` to `gray-500`, and links in running text are underlined.

## Consequences

**Positive**

- Contrast, missing labels, bad ARIA and similar regressions are caught on every pull request, on authenticated pages as well as public ones.
- Runs in the existing Python toolchain; no Node needed for the gate.

**Negative**

- CI needs a Chromium download (`playwright install --with-deps`), adding roughly a minute or two.
- Automated tools find only part of the real problems (roughly a third). They cannot judge keyboard order, focus management, meaningful alt text, screen-reader output or zoom/reflow. Manual testing is still required for new or changed UI.
- The list of scanned pages is maintained by hand; a new page is unchecked until it is added to `tests_a11y/test_axe.py`.
- States that need interaction (open dialogs, error messages, expanded sections, dynamic content loaded by script) are not scanned yet.
- The Lighthouse job is unproven in CI until it first runs, which is why it is report-only.

**Follow-ups**

- Add scans for interactive states (validation errors, open collapsible sections, the audit history panel).
- Add a manual accessibility checklist for UI changes (keyboard-only, screen reader, 200% zoom, mobile).
- Make the accessibility job a required check once it has run cleanly in CI.
