"""Step 5: merge sources, resolve answers and preserve frozen bank IDs."""

import copy
import json
import pathlib
import re

import ids
import store

SCHEMA_VERSION = 1
_LABEL = re.compile(r"^(?:Subdomain\s+)?(\d+\.\d+)\s*:\s*(.+)$", re.IGNORECASE)


def _source_names(config: dict) -> list[str]:
    """Merge order: given, Curated sites, LLM-scrape sources, created."""
    names = ["given"]
    names += [s["name"] for s in config.get("curated_sites") or []]
    names += [s["name"] for s in config.get("llm_sources") or []]
    names.append("created")
    return names


def _text_hash(row: dict) -> str:
    return ids.question_id(row["question"], [c["text"] for c in row["choices"]])


def _given_text(record: dict) -> list:
    """Exact text and order, since the dedupe hash hides punctuation and moves."""
    return [record["question"], [c["text"] for c in record["choices"]]]


def _source_record(record: dict) -> dict:
    given = record["sources"][0]
    return {
        "name": given["name"],
        "url": given.get("url", ""),
        "source_question_no": given.get("source_question_no", ""),
        "site_answer": sorted(set(given.get("site_answer") or [])),
        "community_answer": sorted(set(given.get("community_answer") or [])),
        "scraped_at": given.get("scraped_at", ""),
        "subdomain_label": given.get("subdomain_label", ""),
        "explanation_block": given.get("explanation_block", ""),
        "unsure": bool(given.get("unsure", False)),
    }


def _choices(record: dict, by: str) -> list[dict]:
    out = []
    for letter, choice in zip("ABCDEF", record["choices"]):
        text = choice.get("explanation", "")
        out.append({"letter": letter, "text": choice["text"], "explanation": text,
                    "explanation_by": choice.get("explanation_by", by) if text else ""})
    return out


def _letter_map(from_choices: list[dict], to_choices: list[dict]) -> dict[str, str]:
    """Map letters between two choice orders by normalized choice text."""
    target = {ids.norm(c["text"], choice=True): c["letter"] for c in to_choices}
    return {c["letter"]: target[key] for c in from_choices
            if (key := ids.norm(c["text"], choice=True)) in target}


def _remap(letters: list[str], mapping: dict[str, str]) -> list[str]:
    return sorted(mapping[x] for x in letters if x in mapping)


def _remap_source(source: dict, mapping: dict[str, str]) -> dict:
    source["site_answer"] = _remap(source["site_answer"], mapping)
    source["community_answer"] = _remap(source["community_answer"], mapping)
    return source


def _source_key(source: dict) -> tuple:
    return (source["name"], "" if source["name"] == "given" else source["url"],
            source["source_question_no"])


def _answer_texts(row: dict, letters: list[str]) -> tuple:
    texts = {c["letter"]: ids.norm(c["text"], choice=True) for c in row["choices"]}
    return tuple(sorted(texts[x] for x in letters if x in texts))


def _new_row(record: dict, source: dict, row_id: str, lineage: str) -> dict:
    by = "user" if lineage == "given" else "source"
    subdomain = record.get("subdomain", "") if lineage == "given" else ""
    row = {
        "id": row_id,
        "exam": record["exam"],
        "status": "active",
        "subdomain": subdomain,
        "subdomain_by": "user" if subdomain else "",
        "subdomain_confidence": "",
        "question": record["question"],
        "choices": _choices(record, by),
        "answer": [],
        "answer_by": "",
        "answer_confidence": "",
        "answer_note": "",
        "answer_refs": [],
        "answer_checked_at": "",
        "explanation_by": "",
        "lineage": lineage,
        "sources": [source],
        "uncertain": False,
        "derived_from": [],
        "updated_at": "",
        "rechecked_at": "",
        "recheck_note": "",
    }
    if lineage == "created":
        row.update(copy.deepcopy(record))
        row.update(id=row_id, status="active", lineage="created", sources=[source])
        row["choices"] = _choices(record, "llm")
    elif lineage == "scraped":
        for choice in row["choices"]:
            choice.update(explanation="", explanation_by="")
    return row


def _apply_given_marks(row: dict, record: dict) -> None:
    """What a given block sets on any row it is attached to."""
    row["lineage"] = "given"
    if record.get("subdomain"):
        row["subdomain"] = record["subdomain"]
        row["subdomain_by"] = "user"
        row["subdomain_confidence"] = ""


def _settle_tag(row: dict, titles: dict[str, str]) -> None:
    if row["subdomain_by"] in ("user", "llm"):
        return
    matched = set()
    for source in row["sources"]:
        label = source.get("subdomain_label", "").strip()
        if not label:
            continue
        match = _LABEL.fullmatch(label)
        if not match or match[1] not in titles or ids.norm(match[2]) != ids.norm(titles[match[1]]):
            matched.add("")
        else:
            matched.add(match[1])
    number = next(iter(matched)) if len(matched) == 1 else ""
    row.update(subdomain=number, subdomain_by="source" if number else "",
               subdomain_confidence="")


def _update_given_row(row: dict, record: dict, source: dict, position: int) -> None:
    """A given key update in place: text, choices, ticks, explanations. The ID stays."""
    text_changed = _given_text(row) != _given_text(record)
    old_choices = row["choices"]
    new_choices = _choices(record, "user")
    old_to_new = _letter_map(old_choices, new_choices)
    kept = {old_to_new[c["letter"]]: c for c in old_choices if c["letter"] in old_to_new}

    for choice in new_choices:
        old = kept.get(choice["letter"])
        if old is not None and old["explanation_by"] == "llm" and not text_changed:
            choice.update(explanation=old["explanation"], explanation_by="llm")
        if choice["explanation"] or old is None:
            continue
        # The user's own Why: is gone with its line. LLM text goes when the text changed.
        if old["explanation_by"] == "source" or (
                old["explanation_by"] == "llm" and not text_changed):
            choice["explanation"] = old["explanation"]
            choice["explanation_by"] = old["explanation_by"]

    row["question"] = record["question"]
    row["choices"] = new_choices
    if text_changed:
        row["answer_checked_at"] = ""
        if row["answer_by"] == "llm":
            row.update(answer=[], answer_by="", answer_confidence="",
                       answer_note="", answer_refs=[])
    row["answer"] = _remap(row["answer"], old_to_new)
    for other in row["sources"]:
        _remap_source(other, old_to_new)
    row["sources"][position] = source
    _apply_given_marks(row, record)


def _settle_explanations(row: dict, records: list[tuple[str, dict]]) -> None:
    user, complete = {}, {}
    has_given = any(name == "given" for name, _ in records)
    for name, record in records:
        choices = _choices(record, "user" if name == "given" else "source")
        mapping = _letter_map(choices, row["choices"])
        explanations = {mapping[c["letter"]]: c["explanation"] for c in choices
                        if c["letter"] in mapping and c["explanation"]}
        if name == "given":
            for letter, text in explanations.items():
                user.setdefault(letter, text)
        elif name != "created" and not complete and len(explanations) == len(row["choices"]):
            complete = explanations
    for choice in row["choices"]:
        if choice["explanation_by"] == "llm":
            continue
        letter = choice["letter"]
        if letter in user:
            choice.update(explanation=user[letter], explanation_by="user")
        else:
            if has_given and choice["explanation_by"] == "user":
                choice.update(explanation="", explanation_by="")
            if letter in complete and choice["explanation_by"] != "user":
                choice.update(explanation=complete[letter], explanation_by="source")


def _settle(row: dict, trusted: dict[str, bool], records: list[tuple[str, dict]],
            source_order: dict[str, int]) -> None:
    """Choose the answer and raise uncertainty without clearing earlier evidence."""
    ordered = sorted(row["sources"], key=lambda s: source_order.get(s["name"], len(source_order)))
    given = [s for s in ordered if s["name"] == "given"]
    sure = [s for s in given if not s["unsure"] and s["site_answer"]]
    if sure:
        ticks = sure[0]["site_answer"]
        if ticks != row["answer"]:
            row["answer_checked_at"] = ""
            for choice in row["choices"]:
                if choice["explanation_by"] == "llm":
                    choice.update(explanation="", explanation_by="")
        row["answer"], row["answer_by"] = list(ticks), "user"
    elif row["answer_by"] != "llm":
        unsure = [s for s in given if s["site_answer"]]
        others = [s for s in ordered if s["site_answer"]]
        others.sort(key=lambda s: not trusted.get(s["name"], False))
        if unsure:
            row["answer"], row["answer_by"] = list(unsure[0]["site_answer"]), "user"
        elif others:
            row["answer"], row["answer_by"] = list(others[0]["site_answer"]), "source"
        else:
            row["answer"], row["answer_by"] = [], ""

    answers = {tuple(a) for s in row["sources"]
               for a in (s["site_answer"], s["community_answer"]) if a}
    untrusted_answer = row["answer_by"] == "source" and bool(row["answer"]) and not any(
        trusted.get(s["name"], False) and s["site_answer"] == row["answer"]
        for s in row["sources"])
    if len(answers) > 1 or untrusted_answer or any(s["unsure"] for s in given):
        row["uncertain"] = True       # merge never sets it FALSE

    _settle_explanations(row, records)
    written = [c["explanation_by"] for c in row["choices"] if c["explanation"]]
    if not written:
        row["explanation_by"] = ""
    elif "llm" in written:
        row["explanation_by"] = "llm"
    elif all(by == "user" for by in written):
        row["explanation_by"] = "user"
    else:
        row["explanation_by"] = "source"


def _content(row: dict) -> str:
    """What moves updated_at: question text, choices, answer, explanations."""
    return json.dumps([row["question"], [(c["text"], c["explanation"]) for c in row["choices"]],
                       row["answer"]])


def merge_records(rows: list[dict], sources: list[tuple[str, list[dict]]], now: str,
                  config: dict, given_texts: dict | None = None):
    """Merge source records into rows in place. Return (new count, log events)."""
    events: list[dict] = []
    before: dict[str, str] = {}       # id -> content at first touch in this run
    new_ids: set[str] = set()
    records_by_row: dict[str, list[tuple[str, dict]]] = {}
    trusted = {s["name"]: s.get("answers_trusted", default)
               for key, default in (("curated_sites", True), ("llm_sources", False))
               for s in config.get(key) or []}
    trusted.update(given=True, created=True)
    source_order = {name: i for i, name in enumerate(_source_names(config))}
    old_answers = {(r["id"], _source_key(s)): {
        field: _answer_texts(r, s[field]) for field in ("site_answer", "community_answer")}
        for r in rows for s in r["sources"]}
    titles = store.subdomain_titles(config)
    given_texts = given_texts or {}
    live_keys = {r["sources"][0]["source_question_no"]
                 for name, records in sources if name == "given" for r in records}
    for row in rows:
        for source in row["sources"]:
            if source["name"] == "given" and source["source_question_no"] not in live_keys:
                events.append({"at": now, "step": "merge", "kind": "missing_key",
                               "source": "given", "ref": source["url"],
                               "reason": f"Given key {source['source_question_no']} is no longer in given/. Row kept."})

    def touch(row: dict) -> None:
        before.setdefault(row["id"], _content(row))

    def warn(source: dict, reason: str) -> None:
        events.append({"at": now, "step": "merge", "kind": "warning", "source": source["name"],
                       "ref": f"{source['url']}", "reason": reason})

    def attached(source: dict, hashed: str, by_key_only: bool):
        """The row holding this source record. A row whose text matches wins."""
        found = (None, -1)
        for row in rows:
            for position, held in enumerate(row["sources"]):
                if held["name"] != source["name"]:
                    continue
                if held["source_question_no"] != source["source_question_no"]:
                    continue
                if by_key_only or held["url"] == source["url"]:
                    if hashed in (row["id"], _text_hash(row)):
                        return row, position
                    if found[0] is None:
                        found = (row, position)
        return found

    for name, records in sources:
        lineage = name if name in ("given", "created") else "scraped"
        for record in records:
            if name == "given" and record.get("subdomain") not in titles:
                record = {**record, "subdomain": ""}
            source = _source_record(record)
            incoming = _choices(record, "user" if lineage == "given" else "source")
            hashed = ids.question_id(record["question"], [c["text"] for c in incoming])

            # 1 and 2: the record is already attached to a row.
            row, position = attached(source, hashed, by_key_only=(name == "given"))
            if row is not None:
                same_text = hashed in (row["id"], _text_hash(row))
                # Update any edited given key. Remember each block's own order so
                # an unchanged duplicate does not undo another block's edit.
                previous_text = given_texts.get(source["source_question_no"])
                given_changed = previous_text != _given_text(record) if previous_text is not None else (
                    position == 0 or not same_text)
                if name == "given" and given_changed:
                    touch(row)
                    _update_given_row(row, record, source, position)
                    records_by_row.setdefault(row["id"], []).append((name, record))
                    continue
                if same_text or name == "given":
                    touch(row)
                    if name == "given":
                        _apply_given_marks(row, record)
                    row["sources"][position] = _remap_source(
                        source, _letter_map(incoming, row["choices"]))
                    records_by_row.setdefault(row["id"], []).append((name, record))
                    continue
                warn(source, "Source key matches a row with different text, merged as new.")

            # 3 and 4: dedupe against every stored id and every current-text hash.
            row = next((r for r in rows if hashed in (r["id"], _text_hash(r))), None)
            if row is not None:
                if name == "created":
                    events.append({"at": now, "step": "merge", "kind": "dropped",
                                   "source": name, "ref": source["url"],
                                   "reason": f"Duplicate of {row['id']}."})
                    continue
                touch(row)
                row["sources"].append(_remap_source(source, _letter_map(incoming, row["choices"])))
                if name == "given":
                    _apply_given_marks(row, record)
                records_by_row.setdefault(row["id"], []).append((name, record))
                continue

            # 5: a new row.
            row = _new_row(record, source, hashed, lineage)
            rows.append(row)
            new_ids.add(hashed)
            before[hashed] = ""
            records_by_row.setdefault(row["id"], []).append((name, record))

    for row in rows:
        if row["id"] not in before:
            continue
        _settle(row, trusted, records_by_row.get(row["id"], []), source_order)
        stored = _answer_texts(row, row["answer"])
        for source in row["sources"]:
            previous = old_answers.get((row["id"], _source_key(source)), {})
            for field in ("site_answer", "community_answer"):
                answer = _answer_texts(row, source[field])
                if answer and answer != previous.get(field) and answer != stored:
                    row["answer_checked_at"] = ""
        _settle_tag(row, titles)
        if _content(row) != before[row["id"]]:
            row["updated_at"] = now
    return len(new_ids), events


def run(root: pathlib.Path, exam: str, now: str) -> str:
    config = store.load_exam_config(root, exam)
    folder = store.exam_dir(root, exam)
    bank_path = folder / "bank.jsonl"

    rows = store.read_jsonl(bank_path)
    old_rows = copy.deepcopy(rows)
    state_path = folder / "state.json"
    old_state = store.read_json(state_path, {})
    meta_path = folder / "bank_meta.json"
    old_meta = store.read_json(meta_path, {})
    guide_changed = old_meta.get("guide_version") != str(config["guide_version"])
    tag_events = []
    titles = store.subdomain_titles(config)
    if guide_changed:
        for row in rows:
            if row["subdomain_by"] == "user" and row["subdomain"] in titles:
                continue
            if row["subdomain_by"] == "user" and row["subdomain"]:
                tag_events.append({"at": now, "step": "merge", "kind": "warning",
                                   "source": "given", "ref": row["id"],
                                   "reason": f"Subdomain {row['subdomain']} is missing from the new guide, cleared."})
            row.update(subdomain="", subdomain_by="", subdomain_confidence="")
    names = [name for name in _source_names(config)
             if (folder / "sources" / f"{name}.jsonl").is_file()]
    sources = [(n, store.read_jsonl(folder / "sources" / f"{n}.jsonl")) for n in names]

    new_count, events = merge_records(rows, sources, now, config, old_state.get("given_texts", {}))
    events = tag_events + events
    if guide_changed:
        for row in rows:
            _settle_tag(row, titles)
    changed = sum(1 for old, row in zip(old_rows, rows) if old != row)

    if rows != old_rows or not bank_path.is_file():
        store.write_atomic(bank_path, store.dump_jsonl(rows))

    meta = {**old_meta, "schema_version": SCHEMA_VERSION, "exam": config["slug"],
            "guide_version": str(config["guide_version"])}
    if meta != old_meta:
        store.write_atomic(meta_path, store.dump_json(meta))

    merged = {f"sources/{n}.jsonl": store.sha256_file(folder / "sources" / f"{n}.jsonl")
              for n in names}
    state = {**old_state, "merged": merged}
    given_texts = {r["sources"][0]["source_question_no"]: _given_text(r)
                   for name, records in sources if name == "given" for r in records}
    if given_texts or "given_texts" in old_state:
        state["given_texts"] = given_texts
    if state != old_state:
        store.write_atomic(state_path, store.dump_json(state))

    store.append_log(root, exam, events)
    lines = [f"merge: {new_count} new, {changed} updated, "
             f"{len(rows) - new_count - changed} unchanged, {len(rows)} rows in the bank"]
    lines += [f"  {e['kind']} {e['ref']}: {e['reason']}" for e in events]
    return "\n".join(lines)
