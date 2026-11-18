"""Playwright driver shared by the Curated site scrapers: headed Chromium, one profile per site."""

from __future__ import annotations


class BrowserSession:
    def __init__(self, profile_dir):
        self.profile_dir = profile_dir

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._context = self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir), headless=False, no_viewport=True)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self

    def __exit__(self, *exc):
        try:
            self._context.close()
        finally:
            self._playwright.stop()

    def get_text(self, url: str) -> tuple[int, str]:
        """GET with the profile's own cookies and user agent."""
        response = self._context.request.get(url)
        return response.status, response.text()

    def load(self, url: str) -> str:
        self._page.goto(url, wait_until="domcontentloaded")
        return self._page.content()

    def snapshot(self) -> str:
        """The page as it is. Empty while the user's own navigation is in flight."""
        from playwright.sync_api import Error
        try:
            return self._page.content()
        except Error:
            return ""

    def url(self) -> str:
        return self._page.url
