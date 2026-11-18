"""ExamTopics: page hooks, `parse` and `parse_page`. No browser code lives here.

Selectors were read from the live site, see ticket 08 comments.
"""

from __future__ import annotations

import re

from scrapers import common

AUTH_PATHS = ("/login/", "/signup/")
_PAGE_COUNT = re.compile(r"Viewing page\s+\d+\s+out of\s+(\d+)\s+pages")
_QUESTION_NO = re.compile(r"#\s*(\d+)")
_LETTERS = "ABCDEF"
_SUPPORTS = re.compile(r"Answer\s+([A-F]+)")


def page_url(base: str, page: int) -> str:
    return base if page == 1 else f"{base.rstrip('/')}/{page}/"


def has_cards(html: str) -> bool:
    """A gate is a page with no question cards, not a page with a login modal."""
    return common.soup(html).select_one(".exam-question-card") is not None


def is_paywall(html: str) -> bool:
    """Past the free limit the page holds no question cards and a plan-picker (`.access-plan`).

    The nav and footer say "PRO" on every page, so the plan-picker block is the marker.
    """
    page = common.soup(html)
    return page.select_one(".exam-question-card") is None and page.select_one(".access-plan") is not None


def page_count(html: str) -> int | None:
    match = _PAGE_COUNT.search(common.soup(html).get_text(" "))
    return int(match.group(1)) if match else None


def on_auth_page(url: str) -> bool:
    return any(path in url for path in AUTH_PATHS)


def parse(html: str, url: str) -> tuple[list[dict], list[dict]]:
    """Return (records, skipped). A skipped item is {number, reason}."""
    records, skipped = [], []
    for card in common.soup(html).select(".exam-question-card"):
        header = card.select_one(".card-header strong")
        match = _QUESTION_NO.search(header.get_text()) if header else None
        number = int(match.group(1)) if match else 0
        reason = _skip_reason(card)
        if reason:
            skipped.append({"number": number, "reason": reason})
            continue
        items = card.select("li.multi-choice-item")
        choices, community = [], []
        for item in items:
            letter = item.select_one(".multi-choice-letter")
            letter = letter.get_text().strip(" .") if letter else ""
            if item.select_one(".most-voted-answer-badge"):
                community.append(letter)
            body = common.soup(str(item)).li
            for noise in body.select(".multi-choice-letter, .most-voted-answer-badge"):
                noise.decompose()
            choices.append((letter, common.cell_text(body)))
        if [letter for letter, _ in choices] != list(_LETTERS[:len(choices)]):
            skipped.append({"number": number, "reason": "choice letters out of order"})
            continue
        answer = card.select_one(".question-answer strong.ml-1")
        text = answer.get_text().strip() if answer else ""
        site = sorted(set(re.findall(r"[A-F]", text))) if re.fullmatch(r"[A-F][A-F ,]*", text) else []
        records.append({
            "number": number,
            "stem": common.cell_text(card.select_one(".question-body p.card-text")),
            "choices": [text for _, text in choices],
            "site_answer": [x for x in site if x in _LETTERS[:len(choices)]],
            "community_answer": sorted(set(community) or _community_line(card, len(choices))),
        })
    return records, skipped


def _community_line(card, count: int) -> set[str]:
    """Multi-answer cards tag no option, so read "Community vote currently supports Answer AD"."""
    line = card.select_one(".question-answer p.text-sm span")
    match = _SUPPORTS.fullmatch(line.get_text().strip()) if line else None
    return {x for x in match.group(1) if x in _LETTERS[:count]} if match else set()


def _skip_reason(card) -> str:
    if card.select_one(".question-body p.card-text") is None:
        return "no question text"
    # The vote icon in the answer block is not content, so only stem and choices count.
    if card.select_one("p.card-text img, .question-choices-container img"):
        return "needs an image"
    count = len(card.select("li.multi-choice-item"))
    if count < 2 or count > 6:
        return f"{count} choices, need 2 to 6"
    return ""


def parse_page(html: str, url: str) -> list[dict]:
    """Questions of one page: number, stem, choices, site_answer, community_answer."""
    return parse(html, url)[0]
