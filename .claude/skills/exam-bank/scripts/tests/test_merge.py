import hashlib
import json
import shutil

import pytest
import yaml

import intake
import merge
import store
from conftest import SKILL

T1 = "2026-11-17T08:00:00Z"
T2 = "2026-11-17T09:00:00Z"
T3 = "2026-11-17T10:00:00Z"

# Hashed by hand with hashlib over the normalized text, not through `ids`.
ID_G001 = "q_acf6564191b9"
ID_G002 = "q_131905f1c69b"
ID_G003 = "q_c8e116467ca1"
ID_CHEAPER = "q_76af99db753f"      # "which is cheaper\nondemand vms\nspot vms"


def folder(root):
    return root / "exam-bank" / "pmle"


def bank(root):
    return store.read_jsonl(folder(root) / "bank.jsonl")


def write_given(root, text, name="mine.md"):
    (folder(root) / "given" / name).write_text(text, encoding="utf-8")


def intake_and_merge(root, now):
    intake.run(root, "pmle", now)
    merge.run(root, "pmle", now)


def ship_example(root):
    shutil.copy(SKILL / "templates" / "given-example.md", folder(root) / "given" / "example.md")


def test_merge_creates_one_row_per_new_question_with_the_id_as_computed(root):
    ship_example(root)

    intake_and_merge(root, T1)

    rows = bank(root)
    assert [r["id"] for r in rows] == [ID_G001, ID_G002, ID_G003]
    assert rows[0] == {
        "id": ID_G001,
        "exam": "pmle",
        "status": "active",
        "subdomain": "2.1",
        "subdomain_by": "user",
        "subdomain_confidence": "",
        "question": "Which two steps reduce training-serving skew?",
        "choices": [
            {"letter": "A", "text": "Use the same transform code in training and serving.",
             "explanation": "One code path, so features match at both ends.",
             "explanation_by": "user"},
            {"letter": "B", "text": "Retrain the model every day.",
             "explanation": "Fresh weights do not fix a feature mismatch.",
             "explanation_by": "user"},
            {"letter": "C", "text": "Export the transforms as a TFX Transform graph.",
             "explanation": "", "explanation_by": ""},
            {"letter": "D", "text": "Increase the serving batch size.",
             "explanation": "", "explanation_by": ""},
        ],
        "answer": ["A", "C"],
        "answer_by": "user",
        "answer_confidence": "",
        "answer_note": "",
        "answer_refs": [],
        "answer_checked_at": "",
        "explanation_by": "user",
        "lineage": "given",
        "sources": [{
            "name": "given", "url": "given/example.md#g-001", "source_question_no": "g-001",
            "site_answer": ["A", "C"], "community_answer": [], "scraped_at": T1,
            "subdomain_label": "", "explanation_block": "", "unsure": False,
        }],
        "uncertain": False,
        "derived_from": [],
        "updated_at": T1,
        "rechecked_at": "",
        "recheck_note": "",
    }
    # Unsure: yes makes an Uncertain answer. No ticks leaves the answer empty.
    assert (rows[1]["answer"], rows[1]["answer_by"], rows[1]["uncertain"]) == (["A"], "user", True)
    assert (rows[2]["answer"], rows[2]["answer_by"], rows[2]["uncertain"]) == ([], "", False)
    assert rows[1]["subdomain"] == "" and rows[1]["subdomain_by"] == ""


def test_merge_rerun_on_unchanged_files_changes_nothing(root):
    ship_example(root)
    intake_and_merge(root, T1)
    names = ["bank.jsonl", "bank_meta.json", "state.json"]
    before = [(folder(root) / n).read_bytes() for n in names]

    merge.run(root, "pmle", T2)

    assert [(folder(root) / n).read_bytes() for n in names] == before
    assert not list(folder(root).glob("*.tmp"))


def test_an_edited_given_block_updates_its_row_in_place_and_keeps_the_id(root):
    write_given(root, "## k\nWich is cheaper?\n- [ ] On-demand VMs\n- [x] Spot VMs\n")
    intake_and_merge(root, T1)
    [old] = bank(root)

    # Typo fixed, choices swapped, a Why added.
    write_given(root, "## k\nWhich is cheaper?\n- [x] Spot VMs\n  Why: Preemptible.\n"
                      "- [ ] On-demand VMs\n")
    intake_and_merge(root, T2)

    [row] = bank(root)
    assert row["id"] == old["id"] != ID_CHEAPER      # frozen at first merge, ADR 0001
    assert row["question"] == "Which is cheaper?"
    assert [c["text"] for c in row["choices"]] == ["Spot VMs", "On-demand VMs"]
    assert row["choices"][0]["explanation"] == "Preemptible."
    assert row["answer"] == ["A"]
    assert row["sources"][0]["site_answer"] == ["A"]
    assert len(row["sources"]) == 1
    assert row["updated_at"] == T2


def test_removing_the_ticks_from_a_given_block_empties_the_stored_answer(root):
    write_given(root, "## k\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)

    write_given(root, "## k\nWhich is cheaper?\n- [ ] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T2)

    [row] = bank(root)
    assert row["id"] == ID_CHEAPER
    assert (row["answer"], row["answer_by"]) == ([], "")


def test_a_given_edit_keeps_llm_explanations_only_while_the_text_stands(root):
    write_given(root, "## k\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    [row] = bank(root)
    for choice in row["choices"]:
        choice.update(explanation="Written by the LLM.", explanation_by="llm")
    (folder(root) / "bank.jsonl").write_bytes(store.dump_jsonl([row]))

    # Subdomain line added: text unchanged, so the explanations stay.
    write_given(root, "## k\nSubdomain: 4.1\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T2)
    [row] = bank(root)
    assert [c["explanation_by"] for c in row["choices"]] == ["llm", "llm"]
    assert (row["subdomain"], row["subdomain_by"]) == ("4.1", "user")
    assert row["updated_at"] == T1

    # Choice text changed: every LLM-written explanation is cleared.
    write_given(root, "## k\nSubdomain: 4.1\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] Reserved VMs\n")
    intake_and_merge(root, T3)
    [row] = bank(root)
    assert [c["explanation"] for c in row["choices"]] == ["", ""]
    assert row["updated_at"] == T3


def test_two_given_blocks_with_reordered_choices_become_one_row(root):
    write_given(root, "## first\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n\n"
                      "## second\nwhich is cheaper\n- [ ] B. On-demand VMs\n- [x] A. Spot VMs\n")

    intake_and_merge(root, T1)

    [row] = bank(root)
    assert row["id"] == ID_CHEAPER
    assert [s["source_question_no"] for s in row["sources"]] == ["first", "second"]
    assert [s["site_answer"] for s in row["sources"]] == [["A"], ["A"]]   # remapped to stored order
    assert [c["text"] for c in row["choices"]] == ["Spot VMs", "On-demand VMs"]
    assert row["uncertain"] is False


def scraped_record(scraped_at):
    return {
        "exam": "pmle", "lineage": "scraped", "question": "Which is cheaper?",
        "choices": [{"letter": "A", "text": "Spot VMs"}, {"letter": "B", "text": "On-demand VMs"}],
        "answer": ["A"],
        "sources": [{"name": "examtopics", "url": "https://example.com/view/2/",
                     "source_question_no": "11", "site_answer": ["A"],
                     "community_answer": ["A"], "scraped_at": scraped_at}],
    }


def write_source(root, name, records):
    path = folder(root) / "sources" / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(store.dump_jsonl(records))


def source_record(name, answer, *, community=(), unsure=False, explanations=()):
    record = scraped_record(T1)
    record["answer"] = list(answer)
    record["sources"][0].update(name=name, site_answer=list(answer),
                                community_answer=list(community), unsure=unsure)
    for choice, explanation in zip(record["choices"], explanations):
        choice["explanation"] = explanation
    return record


def configure(root, **changes):
    path = root / "exam-bank/config/exams/pmle.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config.update(changes)
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_first_trusted_source_wins_over_an_earlier_untrusted_source(root):
    configure(root, curated_sites=[{"name": "examtopics", "answers_trusted": False},
                                   {"name": "certsafari"}])
    write_source(root, "examtopics", [source_record("examtopics", ["A"])])
    write_source(root, "certsafari", [source_record("certsafari", ["B"])])

    merge.run(root, "pmle", T1)

    [row] = bank(root)
    assert (row["answer"], row["answer_by"], row["uncertain"]) == (["B"], "source", True)


@pytest.mark.parametrize("records,expected", [
    ([("examtopics", ["A"], {}), ("certsafari", ["B"], {})], True),
    ([("examtopics", ["A"], {"community": ["B"]})], True),
    ([("whizlabs", ["A"], {})], True),
    ([("given", ["A"], {"unsure": True})], True),
    ([("whizlabs", ["A"], {}), ("given", ["A"], {})], False),
    ([("whizlabs", ["A"], {}), ("examtopics", ["A"], {})], False),
    ([("examtopics", [], {"community": ["A"]})], False),
])
def test_uncertain_answer_rules(root, records, expected):
    for name, answer, kwargs in records:
        write_source(root, name, [source_record(name, answer, **kwargs)])

    merge.run(root, "pmle", T1)

    assert bank(root)[0]["uncertain"] is expected


def test_merge_does_not_clear_uncertainty_when_sources_agree_again(root):
    write_source(root, "examtopics", [source_record("examtopics", ["A"], community=["B"])])
    merge.run(root, "pmle", T1)
    write_source(root, "examtopics", [source_record("examtopics", ["A"], community=["A"])])

    merge.run(root, "pmle", T2)

    assert bank(root)[0]["uncertain"] is True


def created_record():
    record = source_record("created", ["A"], explanations=["Correct. Cheaper.", "Incorrect. Dearer."])
    record.update(lineage="created", answer_by="llm", answer_confidence="medium",
                  answer_note="Verified independently.", answer_refs=["https://cloud.google.com/compute/docs"],
                  explanation_by="llm", answer_checked_at=T1, derived_from=[ID_G001],
                  subdomain="3.3", subdomain_by="llm", subdomain_confidence="high")
    for choice in record["choices"]:
        choice["explanation_by"] = "llm"
    return record


def test_created_question_keeps_its_complete_row_and_does_not_drop_itself_on_rerun(root):
    record = created_record()
    write_source(root, "created", [record])

    merge.run(root, "pmle", T1)

    [row] = bank(root)
    for key in ("answer", "answer_by", "answer_confidence", "answer_note", "answer_refs",
                "explanation_by", "answer_checked_at", "derived_from", "subdomain",
                "subdomain_by", "subdomain_confidence", "choices"):
        assert row[key] == record[key], key
    assert row["uncertain"] is False
    before = (folder(root) / "bank.jsonl").read_bytes()
    merge.run(root, "pmle", T2)
    assert (folder(root) / "bank.jsonl").read_bytes() == before
    assert store.read_jsonl(folder(root) / "log.jsonl") == []


def test_created_duplicate_is_dropped_without_touching_the_matching_row(root):
    write_source(root, "examtopics", [source_record("examtopics", ["B"])])
    merge.run(root, "pmle", T1)
    before = (folder(root) / "bank.jsonl").read_bytes()
    write_source(root, "created", [created_record()])

    merge.run(root, "pmle", T2)

    assert (folder(root) / "bank.jsonl").read_bytes() == before
    [event] = store.read_jsonl(folder(root) / "log.jsonl")
    assert (event["kind"], event["source"]) == ("dropped", "created")


def test_explanations_use_user_why_then_first_complete_source_and_protect_llm(root):
    write_source(root, "examtopics", [source_record("examtopics", ["A"], explanations=["Partial."])])
    write_source(root, "certsafari", [source_record("certsafari", ["A"],
                                                    explanations=["Full A.", "Full B."])])
    write_given(root, "## mine\nWhich is cheaper?\n- [x] Spot VMs\n  Why: My reason.\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    [row] = bank(root)
    assert [c["explanation"] for c in row["choices"]] == ["My reason.", "Full B."]
    row["choices"][1].update(explanation="LLM reason.", explanation_by="llm")
    store.write_atomic(folder(root) / "bank.jsonl", store.dump_jsonl([row]))

    merge.run(root, "pmle", T2)

    [row] = bank(root)
    assert [c["explanation"] for c in row["choices"]] == ["My reason.", "LLM reason."]
    assert row["explanation_by"] == "llm"


def test_partial_source_explanations_are_not_stored_as_a_complete_choice_set(root):
    write_source(root, "examtopics", [source_record("examtopics", ["A"], explanations=["Partial."])])
    merge.run(root, "pmle", T1)
    assert [c["explanation"] for c in bank(root)[0]["choices"]] == ["", ""]


@pytest.mark.parametrize("labels,expected", [
    (["Subdomain 4.1: Serving models"], "4.1"),
    (["4.1: SERVING models!"], "4.1"),
    (["4.1"], ""),
    (["Subdomain 4.1: Old title"], ""),
    (["Subdomain 4.1: Serving models", "Subdomain 4.2: Scaling online model serving"], ""),
    (["Subdomain 4.1: Serving models", "Subdomain 4.2: Old title"], ""),
])
def test_source_subdomain_requires_matching_number_and_title_with_no_disagreement(root, labels, expected):
    for name, label in zip(("examtopics", "certsafari"), labels):
        record = source_record(name, ["A"])
        record["sources"][0]["subdomain_label"] = label
        write_source(root, name, [record])

    merge.run(root, "pmle", T1)

    [row] = bank(root)
    assert row["subdomain"] == expected
    assert row["subdomain_by"] == ("source" if expected else "")


def test_valid_given_subdomain_wins_over_conflicting_source_labels(root):
    record = source_record("examtopics", ["A"])
    record["sources"][0]["subdomain_label"] = "Subdomain 4.1: Serving models"
    write_source(root, "examtopics", [record])
    write_given(root, "## k\nSubdomain: 3.3\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    assert (bank(root)[0]["subdomain"], bank(root)[0]["subdomain_by"]) == ("3.3", "user")


def test_guide_change_resets_non_user_tags_and_checks_even_untouched_user_tags(root):
    write_source(root, "examtopics", [source_record("examtopics", ["A"])])
    merge.run(root, "pmle", T1)
    [row] = bank(root)
    row.update(subdomain="4.1", subdomain_by="llm", subdomain_confidence="high")
    user = dict(row, id=ID_G001, subdomain="3.3", subdomain_by="user", sources=[])
    stale = dict(row, id=ID_G002, subdomain="9.9", subdomain_by="user", sources=[])
    labelled = dict(row, id=ID_G003, subdomain="4.2", sources=[{
        **row["sources"][0], "subdomain_label": "Subdomain 4.1: Serving models"}])
    store.write_atomic(folder(root) / "bank.jsonl", store.dump_jsonl([row, user, stale, labelled]))
    configure(root, guide_version="2027-01-01")

    merge.run(root, "pmle", T2)

    rows = bank(root)
    assert [(r["subdomain"], r["subdomain_by"]) for r in rows] == [
        ("", ""), ("3.3", "user"), ("", ""), ("4.1", "source")]
    assert all(r["subdomain_confidence"] == "" for r in (rows[0], rows[2], rows[3]))
    assert [r["updated_at"] for r in rows] == [T1] * 4
    assert store.read_json(folder(root) / "bank_meta.json")["guide_version"] == "2027-01-01"
    assert any(e["kind"] == "warning" and "9.9" in e["reason"]
               for e in store.read_jsonl(folder(root) / "log.jsonl"))


@pytest.mark.parametrize("change", ["punctuation", "reorder", "secondary"])
def test_given_text_edits_clear_llm_work_even_on_a_later_attached_copy(root, change):
    write_source(root, "examtopics", [source_record("examtopics", ["A"])])
    merge.run(root, "pmle", T1)
    write_given(root, "## mine\nWhich is cheaper?\n- [ ] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    [row] = bank(root)
    row.update(answer=["B"], answer_by="llm", answer_checked_at=T1,
               answer_confidence="high", answer_note="LLM view", answer_refs=["ref"],
               subdomain="4.1", subdomain_by="llm")
    for choice in row["choices"]:
        choice.update(explanation="LLM text.", explanation_by="llm")
    store.write_atomic(folder(root) / "bank.jsonl", store.dump_jsonl([row]))
    texts = {
        "punctuation": "Which is cheaper!\n- [ ] Spot VMs\n- [ ] On-demand VMs\n",
        "reorder": "Which is cheaper?\n- [ ] On-demand VMs\n- [ ] Spot VMs\n",
        "secondary": "Which VM costs less?\n- [ ] Spot VMs\n- [ ] On-demand VMs\n",
    }
    write_given(root, "## mine\n" + texts[change])

    intake_and_merge(root, T2)

    [edited] = bank(root)
    assert edited["id"] == row["id"]
    assert edited["question"] == texts[change].splitlines()[0]
    assert edited["answer_by"] != "llm"
    assert edited["answer_checked_at"] == ""
    assert [c["explanation"] for c in edited["choices"]] == ["", ""]
    assert (edited["subdomain"], edited["subdomain_by"]) == ("4.1", "llm")
    before = (folder(root) / "bank.jsonl").read_bytes()
    merge.run(root, "pmle", T3)
    assert (folder(root) / "bank.jsonl").read_bytes() == before


def test_removed_given_block_leaves_row_unchanged_and_logs_missing_key(root):
    write_given(root, "## mine\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    before = (folder(root) / "bank.jsonl").read_bytes()
    write_given(root, "")

    intake_and_merge(root, T2)

    assert (folder(root) / "bank.jsonl").read_bytes() == before
    assert any(e["kind"] == "missing_key" and "mine" in e["ref"]
               for e in store.read_jsonl(folder(root) / "log.jsonl"))


@pytest.mark.parametrize("kind", ["new", "changed", "community", "same", "agrees"])
def test_only_new_or_changed_disagreeing_source_answers_clear_the_check_mark(root, kind):
    write_source(root, "examtopics", [source_record("examtopics", ["A"])])
    merge.run(root, "pmle", T1)
    [row] = bank(root)
    row.update(answer=["B"], answer_by="llm", answer_checked_at=T1)
    store.write_atomic(folder(root) / "bank.jsonl", store.dump_jsonl([row]))
    if kind == "new":
        write_source(root, "certsafari", [source_record("certsafari", ["A"])])
    elif kind == "changed":
        write_source(root, "examtopics", [source_record("examtopics", ["A", "B"])])
    elif kind == "community":
        write_source(root, "examtopics", [source_record("examtopics", ["A"], community=["A"])])
    elif kind == "agrees":
        write_source(root, "certsafari", [source_record("certsafari", ["B"])])

    merge.run(root, "pmle", T2)

    [row] = bank(root)
    assert (row["answer"], row["answer_by"]) == (["B"], "llm")
    assert row["answer_checked_at"] == (T1 if kind in ("same", "agrees") else "")
    before = (folder(root) / "bank.jsonl").read_bytes()
    merge.run(root, "pmle", T3)
    assert (folder(root) / "bank.jsonl").read_bytes() == before


def test_sure_ticks_override_llm_and_clear_only_llm_explanations(root):
    write_source(root, "examtopics", [source_record("examtopics", ["A"])])
    merge.run(root, "pmle", T1)
    [row] = bank(root)
    row.update(answer=["B"], answer_by="llm", answer_checked_at=T1)
    for choice in row["choices"]:
        choice.update(explanation="LLM text.", explanation_by="llm")
    store.write_atomic(folder(root) / "bank.jsonl", store.dump_jsonl([row]))
    write_given(root, "## mine\nWhich is cheaper?\n- [x] Spot VMs\n  Why: My reason.\n- [ ] On-demand VMs\n")

    intake_and_merge(root, T2)

    [row] = bank(root)
    assert (row["answer"], row["answer_by"], row["answer_checked_at"]) == (["A"], "user", "")
    assert [c["explanation"] for c in row["choices"]] == ["My reason.", ""]


def test_removing_a_why_line_removes_its_stored_user_explanation(root):
    write_given(root, "## mine\nWhich is cheaper?\n- [x] Spot VMs\n  Why: My reason.\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    write_given(root, "## mine\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")

    intake_and_merge(root, T2)

    assert bank(root)[0]["choices"][0]["explanation"] == ""


def test_dedupe_uses_both_frozen_id_and_current_text_after_a_given_edit(root):
    write_given(root, "## mine\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    write_given(root, "## mine\nWhich VM costs less?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T2)
    old_text = source_record("examtopics", ["A"])
    current_text = source_record("certsafari", ["A"])
    current_text["question"] = "Which VM costs less?"
    write_source(root, "examtopics", [old_text])
    write_source(root, "certsafari", [current_text])

    merge.run(root, "pmle", T3)

    [row] = bank(root)
    assert row["id"] == ID_CHEAPER
    assert row["question"] == "Which VM costs less?"
    assert [s["name"] for s in row["sources"]] == ["given", "examtopics", "certsafari"]


def test_given_unsure_ticks_beat_trusted_sources_but_leave_an_llm_answer_alone(root):
    write_given(root, "## mine\nUnsure: yes\nWhich is cheaper?\n- [ ] Spot VMs\n- [x] On-demand VMs\n")
    write_source(root, "examtopics", [source_record("examtopics", ["A"])])
    intake_and_merge(root, T1)
    [row] = bank(root)
    assert (row["answer"], row["answer_by"]) == (["B"], "user")
    row.update(answer=["A"], answer_by="llm", answer_checked_at=T1)
    store.write_atomic(folder(root) / "bank.jsonl", store.dump_jsonl([row]))

    merge.run(root, "pmle", T2)

    [row] = bank(root)
    assert (row["answer"], row["answer_by"], row["answer_checked_at"]) == (["A"], "llm", T1)


def test_changing_ticks_on_a_created_row_does_not_restore_its_old_llm_explanations(root):
    write_source(root, "created", [created_record()])
    merge.run(root, "pmle", T1)
    write_given(root, "## mine\nWhich is cheaper?\n- [ ] Spot VMs\n- [x] On-demand VMs\n")

    intake_and_merge(root, T2)

    [row] = bank(root)
    assert row["answer"] == ["B"]
    assert [c["explanation"] for c in row["choices"]] == ["", ""]


def test_moving_a_given_block_to_another_file_preserves_the_check_mark(root):
    write_given(root, "## mine\nUnsure: yes\nWhich is cheaper?\n- [x] Spot VMs\n- [ ] On-demand VMs\n")
    intake_and_merge(root, T1)
    [row] = bank(root)
    row.update(answer=["B"], answer_by="llm", answer_checked_at=T1)
    store.write_atomic(folder(root) / "bank.jsonl", store.dump_jsonl([row]))
    (folder(root) / "given/mine.md").rename(folder(root) / "given/moved.md")

    intake_and_merge(root, T2)

    [row] = bank(root)
    assert row["sources"][0]["url"] == "given/moved.md#mine"
    assert row["answer_checked_at"] == T1


def test_merge_reads_given_then_config_order_then_created(root):
    configure(root, curated_sites=[{"name": "certsafari"}, {"name": "examtopics"}],
              llm_sources=[{"name": "whizlabs"}, {"name": "mockingowl"}])
    for name in ("created", "mockingowl", "examtopics", "given", "whizlabs", "certsafari"):
        record = created_record() if name == "created" else source_record(name, ["A"])
        record["question"] = name
        write_source(root, name, [record])

    merge.run(root, "pmle", T1)

    assert [r["question"] for r in bank(root)] == [
        "given", "certsafari", "examtopics", "whizlabs", "mockingowl", "created"]


def test_an_unordered_multi_answer_is_sorted_before_source_comparisons(root):
    write_source(root, "examtopics", [source_record("examtopics", ["B", "A"])])
    write_source(root, "certsafari", [source_record("certsafari", ["A", "B"])])

    merge.run(root, "pmle", T1)

    [row] = bank(root)
    assert row["answer"] == ["A", "B"]
    assert [s["site_answer"] for s in row["sources"]] == [["A", "B"], ["A", "B"]]
    assert row["uncertain"] is False


def test_merge_reattaches_a_record_the_bank_already_holds(root):
    write_source(root, "examtopics", [scraped_record(T1)])
    merge.run(root, "pmle", T1)
    write_source(root, "examtopics", [scraped_record(T2)])

    merge.run(root, "pmle", T3)

    [row] = bank(root)
    assert row["id"] == ID_CHEAPER
    assert (row["lineage"], row["answer"], row["answer_by"]) == ("scraped", ["A"], "source")
    assert [s["scraped_at"] for s in row["sources"]] == [T2]     # refreshed, not attached twice
    assert row["updated_at"] == T1


def test_a_given_copy_of_a_scraped_question_attaches_and_sets_the_lineage(root):
    write_source(root, "examtopics", [scraped_record(T1)])
    write_given(root, "## mine\nWhich is cheaper?\n- [x] On-demand VMs\n- [ ] Spot VMs\n")

    intake_and_merge(root, T1)

    [row] = bank(root)
    assert [s["name"] for s in row["sources"]] == ["given", "examtopics"]   # given merges first
    assert row["lineage"] == "given"
    assert (row["answer"], row["answer_by"]) == (["A"], "user")
    # The site says Spot VMs, the user ticked On-demand VMs: two source answers differ.
    assert row["sources"][1]["site_answer"] == ["B"]
    assert row["uncertain"] is True


def test_merge_records_source_hashes_and_writes_bank_meta(root):
    ship_example(root)
    intake.run(root, "pmle", T1)
    store.write_atomic(folder(root) / "state.json",
                       store.dump_json({"setup": {"passed_at": T1}}))
    store.write_atomic(folder(root) / "bank_meta.json",
                       store.dump_json({"schema_version": 1, "exam": "pmle",
                                        "guide_version": "2025-01-01", "exported_at": T1,
                                        "section_weights": "1:13"}))

    merge.run(root, "pmle", T2)

    given = (folder(root) / "sources" / "given.jsonl").read_bytes()
    state = json.loads((folder(root) / "state.json").read_text(encoding="utf-8"))
    assert state.pop("given_texts")["g-003"] == [
        "A question with no ticks. Step 7 fills the answer.", ["Choice one", "Choice two"]]
    assert state == {"setup": {"passed_at": T1},
                     "merged": {"sources/given.jsonl": hashlib.sha256(given).hexdigest()}}
    meta = json.loads((folder(root) / "bank_meta.json").read_text(encoding="utf-8"))
    assert meta == {"schema_version": 1, "exam": "pmle", "guide_version": "2026-06-01",
                    "exported_at": T1, "section_weights": "1:13"}


def test_a_scraped_page_position_with_new_text_becomes_a_new_row_once(root):
    write_source(root, "examtopics", [scraped_record(T1)])
    merge.run(root, "pmle", T1)
    moved = scraped_record(T2)
    moved["question"] = "Which is fastest?"       # same page position, another question
    write_source(root, "examtopics", [moved])
    merge.run(root, "pmle", T2)
    before = (folder(root) / "bank.jsonl").read_bytes()

    merge.run(root, "pmle", T3)

    assert [len(r["sources"]) for r in bank(root)] == [1, 1]
    assert (folder(root) / "bank.jsonl").read_bytes() == before


def test_a_given_copy_of_a_stored_scraped_row_is_stable_across_reruns(root):
    write_source(root, "examtopics", [scraped_record(T1)])
    merge.run(root, "pmle", T1)
    write_given(root, "## mine\nSubdomain: 4.1\nwhich is cheaper\n- [x] On-demand VMs\n- [ ] Spot VMs\n")
    intake_and_merge(root, T2)
    before = (folder(root) / "bank.jsonl").read_bytes()

    merge.run(root, "pmle", T3)

    assert (folder(root) / "bank.jsonl").read_bytes() == before
    [row] = bank(root)
    assert row["question"] == "Which is cheaper?"                 # the first source's text stays
    assert [c["text"] for c in row["choices"]] == ["Spot VMs", "On-demand VMs"]
    assert (row["subdomain"], row["subdomain_by"], row["lineage"]) == ("4.1", "user", "given")
    assert row["sources"][1]["site_answer"] == ["B"]
