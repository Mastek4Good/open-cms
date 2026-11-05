"""Fixtures for the accessibility scan.

These tests drive a real browser against a real running copy of the app, so they
live outside `tests/` and are not part of the default `pytest` run. Run them with
`uv run --group a11y pytest tests_a11y` (see docs/development.md).
"""

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEMO_EMAIL = "demo@quickcapture.local"
DEMO_PASSWORD = "demo-password-123"  # noqa: S105 - published local demo credential


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def base_url(tmp_path_factory):
    """Start the app with the seeded demo account and cases on a throwaway DB."""
    port = _free_port()
    db_file = tmp_path_factory.mktemp("a11y") / "a11y.db"
    env = {
        "PATH": "/usr/bin:/bin",
        "FLASK_ENV": "development",
        "DATABASE_URL": f"sqlite:///{db_file}",
        "DEMO_ACCOUNT_ENABLED": "true",
        "DEMO_ACCOUNT_SHARED_MFA": "true",
        "DEMO_CASES_ENABLED": "true",
    }
    code = f"from app import create_app; create_app().run(port={port}, use_reloader=False)"
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{url}/login", timeout=1)  # noqa: S310
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("app did not start for the accessibility scan")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch()
        yield chromium
        chromium.close()


@pytest.fixture(scope="session")
def public_context(browser):
    # bypass_csp lets axe-core be injected; the app's own CSP is tested elsewhere.
    context = browser.new_context(bypass_csp=True)
    yield context
    context.close()


@pytest.fixture(scope="session")
def signed_in_context(browser, base_url):
    """A browser context signed in as the shared demo account (any 6-digit MFA code)."""
    context = browser.new_context(bypass_csp=True)
    page = context.new_page()
    page.goto(f"{base_url}/login")
    page.fill("input[name=email]", DEMO_EMAIL)
    page.fill("input[name=password]", DEMO_PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_url("**/mfa/verify")
    page.fill("input[name=code]", "123456")
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/mfa" not in url and "/login" not in url)
    page.close()
    yield context
    context.close()
