"""Plain HTTP session for a Curated site whose answers sit in the static HTML. No browser, no login."""

from __future__ import annotations

import urllib.error
import urllib.request

from scrapers import common

TIMEOUT_SECONDS = 30


class HttpSession:
    """Same surface as `browser.BrowserSession`. `interactive` is False: no user can clear a gate."""

    interactive = False

    def __init__(self, profile_dir=None):
        self._url = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_text(self, url: str) -> tuple[int, str]:
        request = urllib.request.Request(url, headers={"User-Agent": common.USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.status, response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            return error.code, ""

    def load(self, url: str) -> str:
        status, text = self.get_text(url)
        if status != 200:
            raise RuntimeError(f"HTTP {status} for {url}")
        self._url = url
        return text

    def snapshot(self) -> str:
        return ""

    def url(self) -> str:
        return self._url
