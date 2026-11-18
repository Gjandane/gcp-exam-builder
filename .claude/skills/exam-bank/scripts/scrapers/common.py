"""Rules every Curated site scraper shares: cell text, robots.txt, the gate, one page at a time.

A site module supplies the page hooks and `parse`. The loop here owns resume, the pause,
the gate poll, the per-page save and the progress file. It never touches a browser: the
caller passes a `session` with `load(url)`, `snapshot()` and `url()`.
"""

from __future__ import annotations

import random
import re
import time
import urllib.parse
import urllib.robotparser

from bs4 import BeautifulSoup, NavigableString, Tag

import store

POLL_SECONDS = 5
POLL_LIMIT_SECONDS = 8 * 60
PAUSE_RANGE = (3, 8)
USER_AGENT = "Mozilla/5.0 (compatible; exam-bank)"


# Cell text rule: plain text, line breaks, code in backticks.

def cell_text(node) -> str:
    """HTML to plain text. <br> is a line break, code is wrapped in backticks."""
    parts: list[str] = []

    def walk(item, in_pre=False):
        if isinstance(item, NavigableString):
            text = str(item)
            parts.append(text if in_pre else re.sub(r"\s+", " ", text))
        elif isinstance(item, Tag):
            if item.name in ("script", "style"):
                return
            if item.name == "br":
                parts.append("\n")
            elif item.name == "pre":
                parts.append("```\n" if parts and parts[-1].endswith("\n") else "\n```\n")
                for child in item.children:
                    walk(child, True)
                parts.append("\n```\n")
            elif item.name == "code" and not in_pre:
                parts.append("`")
                for child in item.children:
                    walk(child, in_pre)
                parts.append("`")
            else:
                block = item.name in ("p", "div", "li")
                parts.append("\n" if block else "")
                for child in item.children:
                    walk(child, in_pre)
                parts.append("\n" if block else "")

    walk(node)
    text = "".join(parts).replace("\xa0", " ")
    lines = [line.strip(" \t") for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# robots.txt

def robots_allows(robots_text: str, url: str) -> bool:
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(robots_text.splitlines())
    return parser.can_fetch("*", url) and parser.can_fetch(USER_AGENT, url)


def check_robots(session, site: str, urls: list[str]) -> None:
    """Stop when robots.txt cannot be read or disallows a page URL."""
    parts = urllib.parse.urlsplit(urls[0])
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    status, text = session.get_text(robots_url)
    if status == 404:
        return
    if status != 200:
        raise store.Stop(f"{site}: robots.txt answered {status}, so the scrape cannot confirm the "
                         "site allows it. Nothing was fetched. Rerun later, or put the questions in given/.")
    for url in urls:
        if not robots_allows(text, url):
            raise store.Stop(f"{site}: robots.txt disallows {url}. Nothing was fetched.")


# Files

def progress_path(folder, site):
    return folder / "sources" / f"{site}.progress.json"


def set_gate(root, exam: str, site: str, action: str | None) -> None:
    """Set or clear one site's gate. Read-modify-write, other state keys stay."""
    path = store.exam_dir(root, exam) / "state.json"
    data = store.read_json(path, {})
    gates = dict(data.get("gates", {}))
    if action is None:
        gates.pop(site, None)
    else:
        gates[site] = action
    if gates == data.get("gates", {}):
        return
    data["gates"] = gates
    store.write_atomic(path, store.dump_json(data))


def pages_left(folder, site: str) -> bool:
    progress = store.read_json(progress_path(folder, site), {})
    total = progress.get("pages_total", 0)
    return not total or progress.get("pages_done", 0) < total


# The page loop

def run_site(root, exam: str, site: dict, scraper, session, *,
             sleep=time.sleep, clock=time.monotonic, pause=None, now=store.now_utc) -> list[str]:
    """Scrape the pages left for one site. Return report lines."""
    name, base = site["name"], site["url"]
    folder = store.exam_dir(root, exam)
    pause = pause or (lambda: random.uniform(*PAUSE_RANGE))
    progress = store.read_json(progress_path(folder, name), {})
    total = progress.get("pages_total") or None
    page = progress.get("pages_done", 0) + 1
    action = (f"Log in to {name} in the open browser window, then rerun "
              f"/exam-bank {exam} scrape")
    saved = 0
    first = True
    while total is None or page <= total:
        if not first:
            sleep(pause())
        first = False
        url = scraper.page_url(base, page)
        try:
            html = session.load(url)
        except Exception as error:
            # A redirect (login wall, upsell) aborts the navigation. Read what the window shows.
            html = _page_after_failed_load(scraper, session, url)
            if html is None:
                here = _safe_url(session)
                reason = f"{type(error).__name__}: {str(error).splitlines()[0] if str(error) else ''}"
                if here:
                    reason += f"; window shows {here}"
                store.append_log(root, exam, [{"at": now(), "step": "scrape", "kind": "failed_page",
                                               "source": name, "ref": url, "reason": reason}])
                raise store.Stop(f"{name}: page {page} failed to load ({reason}). "
                                 "Pages saved so far stay. Rerun to continue.") from error
        if not scraper.has_cards(html):
            if not _paywalled(scraper, html):
                if not getattr(session, "interactive", True):
                    raise store.Stop(f"{name}: {url} holds no question cards and no user can clear it "
                                     "over plain HTTP. Nothing was saved. Rerun later, or put the questions in given/.")
                set_gate(root, exam, name, action)
                html = _wait_for_cards(scraper, session, url, sleep, clock)
                if html is None:
                    return [f"{name}: waiting on user: {action}",
                            f"{name}: {saved} page(s) saved, window closed after "
                            f"{POLL_LIMIT_SECONDS // 60} minutes"]
            if html is PAYWALL or _paywalled(scraper, html):
                set_gate(root, exam, name, None)
                return _stop_at_paywall(root, exam, name, folder, page, total, saved, now())
            set_gate(root, exam, name, None)
        if total is None:
            total = scraper.page_count(html)
            if not total:
                raise store.Stop(f"{name}: the page count line was not found on {url}.")
        save_page(root, exam, name, scraper, url, page, total, html, now())
        saved += 1
        page += 1
    return [f"{name}: {saved} page(s) saved, {total}/{total} done"]


PAYWALL = object()   # `_wait_for_cards` found the site's paywall instead of question cards


def _paywalled(scraper, html) -> bool:
    check = getattr(scraper, "is_paywall", None)
    return bool(check and html and check(html))


def _safe_url(session) -> str:
    try:
        return session.url() or ""
    except Exception:
        return ""


def _same_page(a: str, b: str) -> bool:
    return a.rstrip("/") == b.rstrip("/")


def _page_after_failed_load(scraper, session, url):
    """What the window shows after a navigation error, or None when it shows nothing usable.

    Only trust the window when it sits on the page asked for or on a login page. After an
    abort it may still show the previous page, whose cards must never be saved as this one.
    """
    here = _safe_url(session)
    if not here or not (_same_page(here, url) or scraper.on_auth_page(here)):
        return None
    try:
        return session.snapshot() or None
    except Exception:
        return None


def _wait_for_cards(scraper, session, url, sleep, clock):
    """Poll the open window. Never navigate while the user is on a login page.

    Returns the page HTML once it holds cards, PAYWALL when the site's paywall shows on the
    page asked for, or None when the time runs out.
    """
    deadline = clock() + POLL_LIMIT_SECONDS
    away = None, 0
    while clock() < deadline:
        sleep(POLL_SECONDS)
        html = session.snapshot()
        if html and scraper.has_cards(html):
            return html
        here = session.url()
        if _same_page(here or "", url) and _paywalled(scraper, html):
            return PAYWALL
        if not here or here == url or scraper.on_auth_page(here):
            away = None, 0
            continue
        # Off the gate on a page that is not a login page, for example after logging in.
        # Wait until it stays there for two polls before taking the window back.
        away = here, (away[1] + 1 if away[0] == here else 1)
        if away[1] >= 2:
            away = None, 0
            try:
                html = session.load(url)
            except Exception:
                # A redirect aborted the reload. Keep polling what the window shows.
                continue
            if scraper.has_cards(html):
                return html
            if _paywalled(scraper, html):
                return PAYWALL
    return None


def _stop_at_paywall(root, exam, name, folder, page, total, saved, at) -> list[str]:
    """The free limit ends before this page. Record it so the source counts as finished."""
    store.write_atomic(progress_path(folder, name), store.dump_json(
        {"pages_done": page - 1, "pages_total": total or 0, "last_run": at, "paywall_page": page}))
    store.append_log(root, exam, [{"at": at, "step": "scrape", "kind": "paywall", "source": name,
                                   "ref": f"page {page}", "reason": "free limit reached"}])
    return [f"{name}: paywall at page {page}, free limit reached; "
            f"{saved} page(s) saved this run, {page - 1} in all. Continue with the other sources."]


def save_page(root, exam, name, scraper, url, page, total, html, scraped_at) -> None:
    """Raw HTML, then the page's records, then progress. A crash redoes the page."""
    folder = store.exam_dir(root, exam)
    store.write_atomic(folder / "raw" / name / f"page-{page}.html", html.encode("utf-8"))
    records, skipped = scraper.parse(html, url)
    rows = [source_row(exam, name, url, scraped_at, record) for record in records]
    path = folder / "sources" / f"{name}.jsonl"
    kept = [row for row in store.read_jsonl(path) if row["sources"][0]["url"] != url]
    store.write_atomic(path, store.dump_jsonl(kept + rows))
    store.append_log(root, exam, [
        {"at": scraped_at, "step": "scrape", "kind": "skipped", "source": name,
         "ref": f"{url}#{item['number']}", "reason": item["reason"]} for item in skipped])
    store.write_atomic(progress_path(folder, name), store.dump_json(
        {"pages_done": page, "pages_total": total, "last_run": scraped_at}))


def source_row(exam: str, name: str, url: str, scraped_at: str, record: dict) -> dict:
    letters = "ABCDEF"
    explanations = record.get("explanations") or [""] * len(record["choices"])
    return {
        "exam": exam,
        "lineage": "scraped",
        "question": record["stem"],
        "choices": [{"letter": letters[i], "text": text, "explanation": explanations[i]}
                    for i, text in enumerate(record["choices"])],
        "answer": record["site_answer"],
        "sources": [{
            "name": name,
            "url": url,
            "source_question_no": str(record["number"]),
            "site_answer": record["site_answer"],
            "community_answer": record.get("community_answer", []),
            "scraped_at": scraped_at,
            "subdomain_label": record.get("subdomain_label", ""),
            "explanation_block": "",
        }],
    }
