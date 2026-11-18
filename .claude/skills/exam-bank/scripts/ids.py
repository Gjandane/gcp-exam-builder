"""norm and the question ID. Spec 0001, ID rules.

ADR 0001 freezes this algorithm at the first merge. Do not change it.
"""

import hashlib
import re
import unicodedata

_CHOICE_PREFIX = re.compile(r"^\s*\(?[a-f][\.\):]\s+")
_WHITESPACE = re.compile(r"\s+")


def norm(text: str, choice: bool = False) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    if choice:
        text = _CHOICE_PREFIX.sub("", text, count=1)
    text = "".join(
        ch for ch in text
        if ch != "`" and not unicodedata.category(ch).startswith("P")
    )
    return _WHITESPACE.sub(" ", text).strip()


def question_id(question: str, choices: list[str]) -> str:
    lines = [norm(question)] + sorted(norm(c, choice=True) for c in choices)
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return "q_" + digest[:12]
