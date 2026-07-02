"""Cold-load regression test — the app must fully initialise from a fresh page load.

Guards against the 3d669ff class of bug where the trailing init() bootstrap call
was accidentally removed and the tool shipped dead-on-load (empty map dropdown,
no towns) while all parser/unit tests stayed green.

Requires: playwright (python). Serves the repo root itself — no external server.
"""
import http.server
import socketserver
import threading
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PORT = 8137


@pytest.fixture(scope="module")
def server():
    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(REPO), **kw)
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), handler) as httpd:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        yield f"http://127.0.0.1:{PORT}/index.html"
        httpd.shutdown()


def test_cold_load_initialises(server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(server)
        # init() fetches data files then populates the UI; poll up to 10s
        page.wait_for_function(
            "document.querySelectorAll('select')[0] && document.querySelectorAll('select')[0].options.length >= 7",
            timeout=10_000,
        )
        maps_loaded = page.evaluate("mapsData ? Object.keys(mapsData).length : 0")
        towns = page.evaluate(
            "typeof townsData==='object' && townsData ? Object.keys(townsData).length : 0"
        )
        browser.close()

    assert maps_loaded >= 7, f"expected >=7 worlds in mapsData, got {maps_loaded}"
    assert towns >= 1, "seed towns did not load"
    assert not errors, f"console/page errors on cold load: {errors}"
