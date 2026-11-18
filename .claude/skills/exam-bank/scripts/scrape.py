"""Step 2: run the scraper of every enabled Curated site that has pages left."""

import importlib

import store


def scraper_for(name: str):
    """The site's module, or None while it has no scraper yet."""
    try:
        module = importlib.import_module(f"scrapers.{name}")
    except ModuleNotFoundError as error:
        if error.name != f"scrapers.{name}":
            raise
        return None
    return module if hasattr(module, "parse") else None


def run(root, exam, now, open_session=None):
    from scrapers import common   # needs bs4, which setup may still be missing
    config = store.load_exam_config(root, exam)
    folder = store.exam_dir(root, exam)
    injected = open_session
    lines = []
    for site in config.get("curated_sites") or []:
        name = site["name"]
        if not site.get("enabled") or not common.pages_left(folder, name):
            continue
        scraper = scraper_for(name)
        if scraper is None:
            lines.append(f"{name}: no scraper yet, skipped")
            continue
        open_session = injected or _session_class(scraper)
        with open_session(root / "exam-bank" / ".browser" / name) as session:
            common.check_robots(session, name, [scraper.page_url(site["url"], n) for n in (1, 2)])
            lines += common.run_site(root, exam, site, scraper, session,
                                        now=lambda: now)
    return "\n".join(lines) or "scrape: no enabled Curated site has pages left"


def _session_class(scraper):
    """Plain HTTP when the site's static HTML holds the answers, else the headed browser."""
    if getattr(scraper, "FETCH", "browser") == "http":
        from scrapers.http import HttpSession
        return HttpSession
    from scrapers.browser import BrowserSession
    return BrowserSession
