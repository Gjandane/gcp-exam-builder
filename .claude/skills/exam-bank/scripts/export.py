"""Step 10: export the bank as the CSV the study app imports. Spec 0001, Step 10.

The CSV contract binds spec 0002. Change no header, order or format here
without the user.
"""

import csv
import io
import pathlib

import store

LETTERS = "ABCDEF"
HEADER = (
    ["id", "exam", "status", "subdomain", "subdomain_title", "question"]
    + [f"choice_{x.lower()}" for x in LETTERS]
    + ["answer"]
    + [f"explanation_{x.lower()}" for x in LETTERS]
    + ["lineage", "sources", "source_urls", "source_answers", "uncertain", "answer_by",
       "explanation_by", "derived_from", "updated_at", "rechecked_at", "recheck_note"]
)
MAX_LISTED = 20
SKILL = pathlib.Path(__file__).resolve().parents[1]


def missing_parts(row: dict, titles: dict[str, str]) -> list[str]:
    """What an active row still lacks for export. Empty when it is complete."""
    if row["status"] != "active":
        return []
    parts = []
    if not row["answer"]:
        parts.append("answer")
    if not row["subdomain"]:
        parts.append("subdomain")
    elif row["subdomain"] not in titles:
        parts.append(f"subdomain {row['subdomain']} not in the exam config")
    parts += [f"explanation for {c['letter']}" for c in row["choices"]
              if c["text"] and not c["explanation"]]
    return parts


def _cells(row: dict, titles: dict[str, str]) -> list[str]:
    by_letter = {c["letter"]: c for c in row["choices"]}
    source_answers = []
    for source in row["sources"]:
        if source["site_answer"]:
            source_answers.append(f"{source['name']}: {','.join(source['site_answer'])}")
        if source["community_answer"]:
            source_answers.append(
                f"{source['name']}-community: {','.join(source['community_answer'])}")
    return (
        [row["id"], row["exam"], row["status"], row["subdomain"],
         titles.get(row["subdomain"], ""), row["question"]]
        + [by_letter[x]["text"] if x in by_letter else "" for x in LETTERS]
        + [",".join(sorted(row["answer"]))]
        + [by_letter[x]["explanation"] if x in by_letter else "" for x in LETTERS]
        + [row["lineage"],
           "\n".join(s["name"] for s in row["sources"]),
           "\n".join(s["url"] for s in row["sources"]),
           "\n".join(source_answers),
           "TRUE" if row["uncertain"] else "FALSE",
           row["answer_by"], row["explanation_by"],
           "\n".join(row["derived_from"]),
           row["updated_at"], row["rechecked_at"], row["recheck_note"]]
    )


def render_csv(rows: list[dict], config: dict) -> bytes:
    """UTF-8 without a byte order mark, RFC 4180, CRLF row ends, LF inside a cell."""
    titles = store.subdomain_titles(config)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow(_cells(row, titles))
    return buffer.getvalue().encode("utf-8")


def section_weights(config: dict) -> str:
    return ",".join(f"{s['number']}:{s['weight']}" for s in config["sections"])


def render_meta(config: dict, guide_version: str, exported_at: str) -> bytes:
    return store.dump_json({
        "schema_version": 1,
        "exam": config["slug"],
        "guide_version": guide_version,
        "exported_at": exported_at,
        "section_weights": section_weights(config),
    })


def run(root: pathlib.Path, exam: str, now: str) -> str:
    config = store.load_exam_config(root, exam)
    folder = store.exam_dir(root, exam)
    bank_path = folder / "bank.jsonl"
    if not bank_path.is_file():
        raise store.Stop(f"export refused: no bank yet. Run merge for {exam} first.")
    rows = store.read_jsonl(bank_path)
    titles = store.subdomain_titles(config)

    incomplete = [(row["id"], parts) for row in rows if (parts := missing_parts(row, titles))]
    if incomplete:
        lines = [f"export refused: {len(incomplete)} active rows are incomplete, nothing written."
                 f" First {min(len(incomplete), MAX_LISTED)}:"]
        lines += [f"  {row_id}: {', '.join(parts)}" for row_id, parts in incomplete[:MAX_LISTED]]
        raise store.Stop("\n".join(lines))

    # merge owns guide_version. The exam config only fills in when merge has not run.
    meta = store.read_json(folder / "bank_meta.json", {})
    guide_version = meta.get("guide_version", str(config["guide_version"]))

    csv_path = folder / "export" / f"{exam}-questions.csv"
    store.write_atomic(csv_path, render_csv(rows, config))
    store.write_atomic(folder / "bank_meta.json", render_meta(config, guide_version, now))

    active = [r for r in rows if r["status"] == "active"]
    steps = (SKILL / "templates" / "import-steps.txt").read_text(encoding="utf-8")
    return "\n".join([
        f"export: wrote exam-bank/{exam}/export/{exam}-questions.csv",
        f"active: {len(active)}",
        f"retired: {len(rows) - len(active)}",
        f"uncertain: {sum(1 for r in active if r['uncertain'])}",
        f"section_weights: {section_weights(config)}",
        "",
        steps.rstrip("\n"),
    ])
