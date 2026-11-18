import pathlib
import shutil
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
SKILL = SCRIPTS.parent
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def root(tmp_path):
    """An empty repo root holding only the shipped PMLE exam config."""
    exams = tmp_path / "exam-bank" / "config" / "exams"
    exams.mkdir(parents=True)
    shutil.copy(SKILL / "templates" / "exams" / "pmle.example.yaml", exams / "pmle.yaml")
    (tmp_path / "exam-bank" / "pmle" / "given").mkdir(parents=True)
    return tmp_path
