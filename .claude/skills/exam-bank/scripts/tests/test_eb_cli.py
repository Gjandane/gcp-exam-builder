import pathlib
import subprocess
import sys

EB = pathlib.Path(__file__).resolve().parents[1] / "eb.py"


def run_eb(*argv: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(EB), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
    )


def test_unknown_command_exits_non_zero():
    result = run_eb("bogus", "pmle")
    assert result.returncode != 0
    assert "bogus" in result.stderr


def test_known_command_parses_exam(tmp_path):
    result = run_eb("state", "pmle", cwd=tmp_path)
    assert result.returncode == 0
    assert "Current step: setup" in result.stdout


GIVEN = """## g-1
Subdomain: 2.1

Which is cheaper?

- [x] Spot VMs
  Why: Correct. Spot capacity is discounted.
- [ ] On-demand VMs
  Why: Incorrect. On-demand is the list price.
"""


def test_given_file_to_csv_through_the_entry_point(root):
    given = root / "exam-bank" / "pmle" / "given" / "mine.md"
    given.write_text(GIVEN, encoding="utf-8")

    for command in ("intake", "merge", "export"):
        result = run_eb(command, "pmle", cwd=root)
        assert result.returncode == 0, result.stderr
    assert "section_weights: 1:13,2:16,3:21,4:20,5:18,6:13" in result.stdout

    csv_path = root / "exam-bank" / "pmle" / "export" / "pmle-questions.csv"
    lines = csv_path.read_bytes().split(b"\r\n")
    assert lines[0].startswith(b"id,exam,status,subdomain,subdomain_title,question,choice_a,")
    assert lines[1].startswith(b"q_76af99db753f,pmle,active,2.1,")

    # Ticks removed: export refuses and names the ID.
    given.write_text(GIVEN.replace("[x]", "[ ]"), encoding="utf-8")
    assert run_eb("intake", "pmle", cwd=root).returncode == 0
    assert run_eb("merge", "pmle", cwd=root).returncode == 0
    before = csv_path.read_bytes()
    refused = run_eb("export", "pmle", cwd=root)
    assert refused.returncode == 1
    assert "q_76af99db753f: answer" in refused.stderr
    assert csv_path.read_bytes() == before


def test_a_step_stops_with_the_fix_when_the_exam_config_is_missing(tmp_path):
    result = run_eb("intake", "pmle", cwd=tmp_path)
    assert result.returncode == 1
    assert "pmle.yaml" in result.stderr
