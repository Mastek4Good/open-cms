"""WCAG 2.2 AA scan of the main pages using axe-core (the engine Lighthouse uses).

Automated checks find roughly a third of real accessibility problems; they do
not replace keyboard and screen-reader testing. See docs/development.md.
"""

import pytest
from axe_playwright_python.sync_playwright import Axe

WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]

PUBLIC_PAGES = ["/login", "/sign-up"]
SIGNED_IN_PAGES = [
    "/cases",
    "/dashboard",
    "/cases/new",
    "/cases/review",
    "/follow-ups",
    "/reports",
    "/cases/1",
    "/mfa/status",
    "/invite-codes",
    "/users",
]


def _scan(context, url):
    page = context.new_page()
    try:
        response = page.goto(url)
        assert response.status == 200, f"{url} returned {response.status}"
        result = Axe().run(page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}})
    finally:
        page.close()
    return result.response["violations"]


def _format(violations):
    lines = []
    for v in violations:
        lines.append(f"[{v['impact']}] {v['id']}: {v['help']} ({v['helpUrl']})")
        lines.extend(f"    {node['target']}" for node in v["nodes"][:5])
    return "\n".join(lines)


@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_page_has_no_wcag_violations(public_context, base_url, path):
    violations = _scan(public_context, base_url + path)
    assert not violations, "\n" + _format(violations)


@pytest.mark.parametrize("path", SIGNED_IN_PAGES)
def test_signed_in_page_has_no_wcag_violations(signed_in_context, base_url, path):
    violations = _scan(signed_in_context, base_url + path)
    assert not violations, "\n" + _format(violations)
