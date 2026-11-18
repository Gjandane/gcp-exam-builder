"""Golden source files exercise merge and the CSV/state command boundaries."""

import csv
import io
import shutil
import subprocess
import sys

import export
import merge
import store
import yaml

from conftest import FIXTURES, SCRIPTS, SKILL

T1 = "2026-11-17T08:00:00Z"
T2 = "2026-11-17T09:00:00Z"


def prepare_sources(root):
    folder = root / "exam-bank/pmle"
    shutil.copytree(FIXTURES / "merge/sources", folder / "sources")
    config_path = root / "exam-bank/config/exams/pmle.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["curated_sites"][0]["answers_trusted"] = False
    for key in ("curated_sites", "llm_sources"):
        for source in config[key]:
            source["enabled"] = False
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return folder


def test_fixture_sources_merge_to_the_expected_bank_and_rerun_byte_identically(root):
    folder = prepare_sources(root)

    merge.run(root, "pmle", T1)

    assert store.read_jsonl(folder / "bank.jsonl") == store.read_jsonl(FIXTURES / "merge/bank.jsonl")
    before = {name: (folder / name).read_bytes()
              for name in ("bank.jsonl", "bank_meta.json", "state.json")}
    merge.run(root, "pmle", T2)
    assert {name: (folder / name).read_bytes() for name in before} == before


def test_reordered_fixture_sources_export_remapped_answers_and_community_line(root):
    folder = prepare_sources(root)
    merge.run(root, "pmle", T1)

    [row] = store.read_jsonl(folder / "bank.jsonl")
    assert len(row["sources"]) == 2
    assert row["sources"][1]["site_answer"] == ["A"]
    export.run(root, "pmle", T2)

    [csv_row] = csv.DictReader(io.StringIO(
        (folder / "export/pmle-questions.csv").read_bytes().decode("utf-8"), newline=""))
    assert csv_row["sources"] == "examtopics\ncertsafari"
    assert csv_row["source_urls"] == "https://example.com/examtopics/1/\nhttps://example.com/certsafari/"
    assert csv_row["source_answers"] == "examtopics: B\nexamtopics-community: A\ncertsafari: A"
    assert csv_row["answer"] == "A"
    assert csv_row["explanation_a"] == (
        "Correct. Batch prediction reads the whole input file and writes results to storage.")
    assert csv_row["subdomain"] == "4.1"


def test_changed_guide_version_routes_the_cli_state_command_back_to_merge(root):
    folder = prepare_sources(root)
    shutil.copy(SKILL / "templates/models.example.yaml", root / "exam-bank/config/models.yaml")
    store.write_atomic(folder / "state.json", store.dump_json({"setup": {"passed_at": T1}}))
    merge.run(root, "pmle", T1)
    config_path = root / "exam-bank/config/exams/pmle.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["guide_version"] = "2027-01-01"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = subprocess.run([sys.executable, str(SCRIPTS / "eb.py"), "state", "pmle"],
                            cwd=root, capture_output=True, text=True, encoding="utf-8")

    assert result.returncode == 0, result.stderr
    assert "Current step: merge" in result.stdout
    assert "steps/05-merge.md" in result.stdout
    assert "- merge: pending" in (folder / "state.md").read_text(encoding="utf-8")
