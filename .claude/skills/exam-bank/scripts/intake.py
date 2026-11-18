"""Step 4: parse given/*.md into sources/given.jsonl. Spec 0001, Step 4."""

import pathlib
import re

import store

_HEADING = re.compile(r"^##\s+(\S.*?)\s*$")
_CHOICE = re.compile(r"^- \[([ xX])\]\s+(.*)$")
_WHY = re.compile(r"^\s+Why:\s*(.*)$")
_SUBDOMAIN = re.compile(r"^Subdomain:\s*(\S+)\s*$")
_UNSURE = re.compile(r"^Unsure:\s*(\S+)\s*$")
_FENCE = ("```", "~~~")


def _split_blocks(text: str) -> list[dict]:
    """Cut a file into blocks at `## <key>` headings outside code fences.

    Each block line is (text, literal). A fence line and every line inside the
    fence are literal: plain text, whatever they look like.
    """
    blocks, fence = [], ""            # fence holds the marker that opened it
    for number, line in enumerate(text.split("\n"), start=1):
        marker = next((m for m in _FENCE if line.strip().startswith(m)), "")
        literal = bool(fence or marker)
        if fence and marker == fence:
            fence = ""
        elif not fence:
            fence = marker
        heading = None if literal else _HEADING.match(line)
        if heading:
            blocks.append({"key": heading.group(1), "line": number, "lines": []})
        elif blocks:
            blocks[-1]["lines"].append((line, literal))
    return blocks


def _join(lines: list[str]) -> str:
    return "\n".join(lines).strip()


def _parse_block(block: dict) -> dict:
    """Return the parsed block, with `error` set when it is a bad block."""
    subdomain, unsure, has_image = "", False, False
    question: list[str] = []
    choices: list[dict] = []
    stage = "meta"

    for line, literal in block["lines"]:
        if not literal and "![" in line:
            has_image = True

        if stage == "meta":
            if not line.strip():
                continue
            if not literal and (m := _SUBDOMAIN.match(line)):
                subdomain = m.group(1)
                continue
            if not literal and (m := _UNSURE.match(line)):
                unsure = m.group(1).lower() == "yes"
                continue
            stage = "question"

        choice = None if literal else _CHOICE.match(line)
        if choice:
            stage = "choices"
            choices.append({"ticked": choice.group(1) != " ",
                            "text": [choice.group(2)], "why": None})
        elif stage == "question":
            question.append(line.rstrip())
        else:
            current = choices[-1]
            why = None if literal or current["why"] is not None else _WHY.match(line)
            if why:
                current["why"] = [why.group(1)]
            else:
                part = line.rstrip() if literal else line.strip()
                (current["text"] if current["why"] is None else current["why"]).append(part)

    parsed = {
        "key": block["key"], "line": block["line"], "subdomain": subdomain,
        "unsure": unsure, "question": _join(question),
        "choices": [{"ticked": c["ticked"], "text": _join(c["text"]),
                     "why": _join(c["why"] or [])} for c in choices],
        "error": "",
    }
    count = len(choices)
    if has_image:
        parsed["error"] = "image: a question that needs an image is out of scope"
    elif not parsed["question"]:
        parsed["error"] = "no question text"
    elif not 2 <= count <= 6:
        parsed["error"] = f"{count} choice{'' if count == 1 else 's'}, need 2 to 6"
    return parsed


def _record(exam: str, parsed: dict, file_name: str, now: str) -> dict:
    letters = "ABCDEF"
    choices = []
    for letter, choice in zip(letters, parsed["choices"]):
        entry = {"letter": letter, "text": choice["text"]}
        if choice["why"]:
            entry["explanation"] = choice["why"]
            entry["explanation_by"] = "user"
        choices.append(entry)
    ticks = [letter for letter, c in zip(letters, parsed["choices"]) if c["ticked"]]
    record = {"exam": exam, "lineage": "given"}
    if parsed["subdomain"]:
        record["subdomain"] = parsed["subdomain"]
    record.update({
        "question": parsed["question"],
        "choices": choices,
        "answer": ticks,
        "sources": [{
            "name": "given",
            "url": f"given/{file_name}#{parsed['key']}",
            "source_question_no": parsed["key"],
            "site_answer": ticks,
            "scraped_at": now,
            "unsure": parsed["unsure"],
        }],
    })
    return record


def run(root: pathlib.Path, exam: str, now: str) -> str:
    config = store.load_exam_config(root, exam)
    known = store.subdomain_titles(config)
    folder = store.exam_dir(root, exam)
    files = sorted((folder / "given").glob("*.md"), key=lambda p: p.name)
    # With the last file gone, an old given.jsonl is still rewritten, to empty.
    if not files and not (folder / "sources" / "given.jsonl").is_file():
        return f"intake: no files in exam-bank/{exam}/given/, nothing to do"

    records, events, seen = [], [], set()

    def log(kind: str, ref: str, reason: str) -> None:
        events.append({"at": now, "step": "intake", "kind": kind,
                       "source": "given", "ref": ref, "reason": reason})

    for path in files:
        # Text mode, so a CRLF file stores LF.
        text = path.read_text(encoding="utf-8-sig")
        for block in _split_blocks(text):
            parsed = _parse_block(block)
            ref = f"given/{path.name}:{parsed['line']}"
            if not parsed["error"] and parsed["key"] in seen:
                parsed["error"] = f"duplicate key {parsed['key']}"
            if parsed["error"]:
                log("bad_block", ref, parsed["error"])
                continue
            seen.add(parsed["key"])
            if parsed["subdomain"] and parsed["subdomain"] not in known:
                log("warning", ref,
                    f"Subdomain {parsed['subdomain']} is not in the exam config, dropped")
                parsed["subdomain"] = ""
            records.append(_record(exam, parsed, path.name, now))

    store.write_atomic(folder / "sources" / "given.jsonl", store.dump_jsonl(records))
    store.append_log(root, exam, events)

    lines = [f"intake: {len(records)} questions from {len(files)} files"]
    lines += [f"  {e['kind']} {e['ref']}: {e['reason']}" for e in events]
    return "\n".join(lines)
