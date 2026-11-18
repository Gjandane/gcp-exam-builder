"""Files of the data folder: paths, the exam config, JSON and JSONL I/O, the log."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib


class Stop(Exception):
    """A step cannot run. The message tells the user the fix."""


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def exam_dir(root: pathlib.Path, exam: str) -> pathlib.Path:
    return pathlib.Path(root) / "exam-bank" / exam


def load_exam_config(root: pathlib.Path, exam: str) -> dict:
    path = pathlib.Path(root) / "exam-bank" / "config" / "exams" / f"{exam}.yaml"
    if not path.is_file():
        raise Stop(
            f"Missing exam config {path.as_posix()}. Copy "
            ".claude/skills/exam-bank/templates/exams/pmle.example.yaml there."
        )
    try:
        import yaml
    except ImportError as error:
        raise Stop('Missing yaml. Run pip install -r requirements.txt.') from error
    with open(path, encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    if not isinstance(config, dict) or config.get("slug") != exam:
        raise Stop(f"{path.as_posix()} must set slug: {exam}, the file name.")
    return config


def subdomain_titles(config: dict) -> dict[str, str]:
    return {
        str(sub["number"]): sub["title"]
        for section in config["sections"]
        for sub in section["subdomains"]
    }


def read_json(path: pathlib.Path, default=None):
    if not path.is_file():
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def dump_json(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def dump_jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def write_atomic(path: pathlib.Path, data: bytes) -> None:
    """Write through a temp file and a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_log(root: pathlib.Path, exam: str, events: list[dict]) -> None:
    """Append events {at, step, kind, source, ref, reason} to log.jsonl."""
    if not events:
        return
    path = exam_dir(root, exam) / "log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
