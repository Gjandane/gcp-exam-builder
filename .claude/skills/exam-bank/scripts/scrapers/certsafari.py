"""CertSafari sample page: page hooks, `parse` and `parse_page`. No browser code lives here.

Answers and explanations sit in closed `details` elements of the static HTML, so `FETCH` is
"http". Selectors were read from the live page, see ticket 09 comments.
"""

from __future__ import annotations

import re

from bs4 import Comment

from scrapers import common

FETCH = "http"
_LETTERS = "ABCDEF"
_ANSWER = re.compile(r"Correct answers?\s*:\s*([A-F](?:\s*,\s*[A-F])*)")


def page_url(base: str, page: int) -> str:
    return base


def has_cards(html: str) -> bool:
    return common.soup(html).select_one("article details") is not None


def page_count(html: str) -> int | None:
    """The sample page is one page, with no pagination."""
    return 1 if has_cards(html) else None


def on_auth_page(url: str) -> bool:
    return False


def parse(html: str, url: str) -> tuple[list[dict], list[dict]]:
    """Return (records, skipped). A skipped item is {number, reason}."""
    records, skipped = [], []
    for position, article in enumerate(common.soup(html).select("article"), start=1):
        heading = article.find("h3")
        number_span = heading.find("span") if heading else None
        digits = re.search(r"\d+", number_span.get_text()) if number_span else None
        number = int(digits.group()) if digits else position
        reason = _skip_reason(article, heading)
        if reason:
            skipped.append({"number": number, "reason": reason})
            continue
        choices = _choices(article)
        letters = [letter for letter, _ in choices]
        if letters != list(_LETTERS[:len(choices)]):
            skipped.append({"number": number, "reason": "choice letters out of order"})
            continue
        answer = _answer(article, letters)
        if not answer:
            skipped.append({"number": number, "reason": "no answer line"})
            continue
        label = article.find("p", recursive=False)
        records.append({
            "number": number,
            "stem": _stem(heading),
            "choices": [text for _, text in choices],
            "site_answer": answer,
            "explanations": _explanations(article, letters),
            "subdomain_label": common.cell_text(label) if label else "",
        })
    return records, skipped


def parse_page(html: str, url: str) -> list[dict]:
    """Questions of the page: number, stem, choices, site_answer, explanations, subdomain_label."""
    return parse(html, url)[0]


def _skip_reason(article, heading) -> str:
    if heading is None:
        return "no question text"
    if article.select("h3 img, ol img"):
        return "needs an image"
    count = len(article.select("ol > li"))
    if count < 2 or count > 6:
        return f"{count} choices, need 2 to 6"
    return ""


def _stem(heading) -> str:
    """The heading minus its position span and the trailing "(Select N)" span."""
    copy = common.soup(str(heading)).h3
    for span in copy.find_all("span", recursive=False):
        span.decompose()
    return common.cell_text(copy)


def _choices(article) -> list[tuple[str, str]]:
    out = []
    for item in article.select("ol > li"):
        spans = item.find_all("span", recursive=False)
        letter = spans[0].get_text().strip(" .") if spans else ""
        text = common.cell_text(spans[1]) if len(spans) > 1 else ""
        out.append((letter, text))
    return out


def _answer(article, letters: list[str]) -> list[str]:
    line = article.select_one("details > div > p")
    if line is None:
        return []
    own = "".join(str(piece) for piece in line.find_all(string=True, recursive=False)
                  if not isinstance(piece, Comment))
    match = _ANSWER.search(own)
    found = sorted(set(re.findall(r"[A-F]", match.group(1)))) if match else []
    return [x for x in found if x in letters]


def _explanations(article, letters: list[str]) -> list[str]:
    """One text per choice in choice order, "" where the page gave none."""
    by_letter = {}
    for item in article.select("details > div > ul > li"):
        copy = common.soup(str(item)).li
        first = copy.find("span")
        letter = first.get_text().strip(" .") if first else ""
        if first:
            first.decompose()
        by_letter[letter] = common.cell_text(copy)
    return [by_letter.get(letter, "") for letter in letters]
