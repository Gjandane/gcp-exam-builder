import shutil

import intake
import store
from conftest import SKILL

NOW = "2026-11-17T08:00:00Z"


def given_dir(root):
    return root / "exam-bank" / "pmle" / "given"


def write_given(root, name, text):
    (given_dir(root) / name).write_text(text, encoding="utf-8")


def records(root):
    return store.read_jsonl(root / "exam-bank" / "pmle" / "sources" / "given.jsonl")


def log(root):
    return store.read_jsonl(root / "exam-bank" / "pmle" / "log.jsonl")


def source(key, answer, unsure=False, file="example.md"):
    return {"name": "given", "url": f"given/{file}#{key}", "source_question_no": key,
            "site_answer": answer, "scraped_at": NOW, "unsure": unsure}


def test_intake_parses_the_shipped_given_example(root):
    shutil.copy(SKILL / "templates" / "given-example.md", given_dir(root) / "example.md")

    intake.run(root, "pmle", NOW)

    assert records(root) == [
        {
            "exam": "pmle",
            "lineage": "given",
            "subdomain": "2.1",
            "question": "Which two steps reduce training-serving skew?",
            "choices": [
                {"letter": "A", "text": "Use the same transform code in training and serving.",
                 "explanation": "One code path, so features match at both ends.",
                 "explanation_by": "user"},
                {"letter": "B", "text": "Retrain the model every day.",
                 "explanation": "Fresh weights do not fix a feature mismatch.",
                 "explanation_by": "user"},
                {"letter": "C", "text": "Export the transforms as a TFX Transform graph."},
                {"letter": "D", "text": "Increase the serving batch size."},
            ],
            "answer": ["A", "C"],
            "sources": [source("g-001", ["A", "C"])],
        },
        {
            "exam": "pmle",
            "lineage": "given",
            "question": "Which command prints the active project?\n\n"
                        "```bash\ngcloud config list\n```",
            "choices": [
                {"letter": "A", "text": "`gcloud config get-value project`"},
                {"letter": "B", "text": "`gcloud projects describe`"},
                {"letter": "C", "text": "`gcloud auth list`"},
            ],
            "answer": ["A"],
            "sources": [source("g-002", ["A"], unsure=True)],
        },
        {
            "exam": "pmle",
            "lineage": "given",
            "question": "A question with no ticks. Step 7 fills the answer.",
            "choices": [
                {"letter": "A", "text": "Choice one"},
                {"letter": "B", "text": "Choice two"},
            ],
            "answer": [],
            "sources": [source("g-003", [])],
        },
    ]
    assert log(root) == []


def test_intake_skips_and_logs_each_bad_block_by_file_and_line(root):
    write_given(root, "a.md", "\n".join([
        "ignored text before the first heading",       # 1
        "## one-choice",                               # 2
        "Stem",
        "- [x] only",
        "## seven-choices",                            # 5
        "Stem",
        "- [x] 1", "- [ ] 2", "- [ ] 3", "- [ ] 4", "- [ ] 5", "- [ ] 6", "- [ ] 7",
        "## no-text",                                  # 14
        "Subdomain: 2.1",
        "",
        "- [x] yes",
        "- [ ] no",
        "## image",                                    # 19
        "Look at ![diagram](x.png)",
        "- [x] yes",
        "- [ ] no",
        "## good",                                     # 23
        "Stem",
        "- [x] yes",
        "- [ ] no",
        "",
    ]))
    write_given(root, "b.md", "## good\nSame key again\n- [x] yes\n- [ ] no\n")

    intake.run(root, "pmle", NOW)

    assert [r["sources"][0]["url"] for r in records(root)] == ["given/a.md#good"]
    events = log(root)
    assert [(e["kind"], e["ref"]) for e in events] == [
        ("bad_block", "given/a.md:2"),
        ("bad_block", "given/a.md:5"),
        ("bad_block", "given/a.md:14"),
        ("bad_block", "given/a.md:19"),
        ("bad_block", "given/b.md:1"),
    ]
    reasons = [e["reason"] for e in events]
    assert "1 choice" in reasons[0]
    assert "7 choices" in reasons[1]
    assert "no question text" in reasons[2]
    assert "image" in reasons[3]
    assert "duplicate key" in reasons[4]
    assert all(e["step"] == "intake" and e["source"] == "given" and e["at"] == NOW
               for e in events)


def test_intake_treats_lines_inside_a_code_fence_as_text(root):
    write_given(root, "a.md", "\n".join([
        "## fenced",
        "What does this print?",
        "```md",
        "## not-a-heading",
        "- [x] not a choice",
        "![not an image](x.png)",
        "```",
        "- [ ] one",
        "- [x] two",
        "",
    ]))

    intake.run(root, "pmle", NOW)

    [record] = records(root)
    assert record["question"] == (
        "What does this print?\n```md\n## not-a-heading\n- [x] not a choice\n"
        "![not an image](x.png)\n```")
    assert [c["text"] for c in record["choices"]] == ["one", "two"]
    assert record["answer"] == ["B"]
    assert log(root) == []


def test_intake_drops_a_subdomain_missing_from_the_exam_config_with_a_warning(root):
    write_given(root, "a.md", "## k\nSubdomain: 9.9\nStem\n- [x] yes\n- [ ] no\n")

    intake.run(root, "pmle", NOW)

    [record] = records(root)
    assert "subdomain" not in record
    [event] = log(root)
    assert (event["kind"], event["ref"]) == ("warning", "given/a.md:1")
    assert "9.9" in event["reason"]


def test_intake_reads_a_multi_line_why_and_crlf_files(root):
    (given_dir(root) / "a.md").write_bytes(
        b"## k\r\nStem\r\n- [x] yes\r\n  Why: First line.\r\n  Second line.\r\n- [ ] no\r\n")

    intake.run(root, "pmle", NOW)

    [record] = records(root)
    assert record["question"] == "Stem"
    assert record["choices"][0]["explanation"] == "First line.\nSecond line."
    assert record["choices"][1] == {"letter": "B", "text": "no"}


def test_intake_keeps_a_fence_open_until_its_own_marker_closes_it(root):
    write_given(root, "a.md", "## k\nStem\n```\n~~~\n## inside\n```\n- [x] yes\n- [ ] no\n")

    intake.run(root, "pmle", NOW)

    [record] = records(root)
    assert record["question"] == "Stem\n```\n~~~\n## inside\n```"


def test_intake_empties_the_source_file_when_the_last_given_file_is_gone(root):
    write_given(root, "a.md", "## k\nStem\n- [x] yes\n- [ ] no\n")
    intake.run(root, "pmle", NOW)
    (given_dir(root) / "a.md").unlink()

    intake.run(root, "pmle", NOW)

    assert records(root) == []
