import copy
import pathlib
import re
import shutil

import pytest

import export
import store
from conftest import FIXTURES, SKILL

NOW = "2026-11-17T10:00:00Z"
GOLDEN = FIXTURES / "export"
SPEC = pathlib.Path(__file__).resolve().parents[5] / "docs" / "specs" / "0001-exam-bank-skill.md"

HEADER = (
    "id,exam,status,subdomain,subdomain_title,question,choice_a,choice_b,choice_c,choice_d,"
    "choice_e,choice_f,answer,explanation_a,explanation_b,explanation_c,explanation_d,"
    "explanation_e,explanation_f,lineage,sources,source_urls,source_answers,uncertain,"
    "answer_by,explanation_by,derived_from,updated_at,rechecked_at,recheck_note"
)


def folder(root):
    return root / "exam-bank" / "pmle"


def seed(root, rows=None):
    if rows is None:
        shutil.copy(GOLDEN / "bank.jsonl", folder(root) / "bank.jsonl")
    else:
        (folder(root) / "bank.jsonl").write_bytes(store.dump_jsonl(rows))
    # What merge leaves behind.
    (folder(root) / "bank_meta.json").write_bytes(store.dump_json(
        {"schema_version": 1, "exam": "pmle", "guide_version": "2026-06-01"}))


def test_export_writes_the_golden_csv_and_bank_meta_byte_for_byte(root):
    seed(root)

    export.run(root, "pmle", NOW)

    csv_bytes = (folder(root) / "export" / "pmle-questions.csv").read_bytes()
    assert csv_bytes == (GOLDEN / "pmle-questions.csv").read_bytes()
    assert csv_bytes.split(b"\r\n")[0].decode("utf-8") == HEADER
    assert not csv_bytes.startswith(b"\xef\xbb\xbf")
    assert (folder(root) / "bank_meta.json").read_bytes() == (GOLDEN / "bank_meta.json").read_bytes()


def test_export_prints_counts_section_weights_and_the_import_steps(root):
    seed(root)

    out = export.run(root, "pmle", NOW)

    lines = out.splitlines()
    assert "active: 3" in lines
    assert "retired: 1" in lines
    assert "uncertain: 1" in lines
    assert "section_weights: 1:13,2:16,3:21,4:20,5:18,6:13" in lines
    steps = (SKILL / "templates" / "import-steps.txt").read_text(encoding="utf-8")
    assert steps.strip() in out


def test_export_refuses_incomplete_active_rows_and_writes_nothing(root):
    good = store.read_jsonl(GOLDEN / "bank.jsonl")[0]

    def variant(row_id, **changes):
        row = copy.deepcopy(good)
        row["id"] = row_id
        row.update(changes)
        return row

    no_explanation = variant("q_000000000003")
    no_explanation["choices"][1].update(explanation="", explanation_by="")
    rows = [
        good,
        variant("q_000000000001", answer=[]),
        variant("q_000000000002", subdomain=""),
        no_explanation,
        variant("q_000000000004", status="retired", answer=[], subdomain=""),   # retired is exempt
    ] + [variant(f"q_0000000001{n:02d}", answer=[]) for n in range(20)]
    seed(root, rows)
    meta_before = (folder(root) / "bank_meta.json").read_bytes()

    with pytest.raises(store.Stop) as stop:
        export.run(root, "pmle", NOW)

    message = str(stop.value)
    assert "q_000000000001: answer" in message
    assert "q_000000000002: subdomain" in message
    assert "q_000000000003: explanation for B" in message
    assert "q_000000000004" not in message
    assert good["id"] not in message
    assert len(re.findall(r"^\s*q_[0-9a-f]{12}: ", message, re.M)) == 20
    assert "23" in message                      # the full count of incomplete rows
    assert not (folder(root) / "export").exists()
    assert (folder(root) / "bank_meta.json").read_bytes() == meta_before


def spec_block(marker, fence):
    spec = SPEC.read_text(encoding="utf-8")
    start = spec.index(marker)
    match = re.search(rf"\n{fence}[a-z]*\n(.*?)\n{fence}\n", spec[start:], re.S)
    return match.group(1) + "\n"


def test_the_given_example_template_ships_exactly_the_spec_content():
    shipped = (SKILL / "templates" / "given-example.md").read_text(encoding="utf-8")
    assert shipped == spec_block("`templates/given-example.md` ships with exactly", "~~~")


def test_the_import_steps_template_ships_the_spec_wording():
    shipped = (SKILL / "templates" / "import-steps.txt").read_text(encoding="utf-8")
    assert shipped == spec_block("`templates/import-steps.txt`, wording from D209", "```")
