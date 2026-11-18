from pathlib import Path
import runpy

import pytest

check = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'check.py'))
check_readme, check_docs = check['check_readme'], check['check_docs']

STEPS = 'Import into the sheet:\n1. Pick export/<slug>-questions.csv.\n2. Comma.\n'
README_STEPS = 'Import into the sheet:\n1. Pick exam-bank/pmle/export/pmle-questions.csv.\n2. Comma.\n'


@pytest.fixture
def docs(tmp_path):
    config = tmp_path / '.claude/skills/exam-bank/templates/exams/pmle.example.yaml'
    config.parent.mkdir(parents=True)
    config.write_text('curated_sites:\n  - name: forbidden-site\nllm_sources: []\n', encoding='utf-8')
    (tmp_path / 'guide.md').write_text('# Guide\n\n## Setup\n\n## Setup\n\n```text\n## Fake\n```\n', encoding='utf-8')
    return tmp_path


def test_valid_local_and_duplicate_heading_links(docs):
    (docs / 'README.md').write_text('# Start\n[local](#start) [setup](guide.md#setup) [duplicate](guide.md#setup-1)\n', encoding='utf-8')
    assert check_readme(docs) == []


@pytest.mark.parametrize('link, error', [
    ('missing.md', 'missing link target'),
    ('guide.md#missing', 'missing heading'),
    ('guide.md#fake', 'missing heading'),
])
def test_broken_links_fail_with_location(docs, link, error):
    (docs / 'README.md').write_text(f'# Start\n[broken]({link})\n', encoding='utf-8')
    failures = check_readme(docs)
    assert len(failures) == 1
    assert failures[0].startswith('README.md:2: ' + error)


def test_question_site_names_are_rejected_case_insensitively(docs):
    (docs / 'README.md').write_text('# Start\nFORBIDDEN-SITE\n', encoding='utf-8')
    assert 'question-site name' in check_readme(docs)[0]


def test_copied_permissions_are_rejected(docs):
    (docs / 'README.md').write_text('# Start\n```json\n{"permissions": {"allow": []}}\n```\n', encoding='utf-8')
    assert 'permissions block' in check_readme(docs)[0]


def test_bare_placeholder_fails_and_code_placeholder_passes(docs):
    (docs / 'README.md').write_text('# Start\nClick "Go to `<sheet name>`".\n```\nclasp <id>\n```\nOpen <sheet name>.\n', encoding='utf-8')
    assert check_readme(docs) == ['README.md:6: put <sheet name> in backticks; GitHub hides it as an HTML tag']


def test_bare_placeholder_in_a_spec_fails(docs):
    (docs / 'README.md').write_text('# Start\n', encoding='utf-8')
    (docs / 'docs/specs').mkdir(parents=True)
    (docs / 'docs/specs/0002-app.md').write_text('# App\nupdated <date>\n', encoding='utf-8')
    assert check_docs(docs) == ['docs/specs/0002-app.md:2: put <date> in backticks; GitHub hides it as an HTML tag']


def write_import_steps(docs, readme=README_STEPS, spec=STEPS, server=None):
    template = docs / '.claude/skills/exam-bank/templates/import-steps.txt'
    template.write_text(STEPS, encoding='utf-8')
    (docs / 'docs/specs').mkdir(parents=True)
    for name in ('0001-exam-bank-skill.md', '0002-study-app.md'):
        (docs / 'docs/specs' / name).write_text(f'# Spec\n```\n{spec}```\n', encoding='utf-8')
    (docs / 'README.md').write_text(f'# Start\n```text\n{readme}```\n', encoding='utf-8')
    lines = server if server is not None else STEPS.splitlines()
    (docs / 'app/server').mkdir(parents=True)
    body = ''.join(f"  '{line}',\n" for line in lines)
    (docs / 'app/server/server.js').write_text(f"var IMPORT_STEPS_ = [\n{body}].join('\\n');\n", encoding='utf-8')


def test_import_steps_copies_match(docs):
    write_import_steps(docs)
    assert check_docs(docs) == []


@pytest.mark.parametrize('change, culprit', [
    ({'readme': STEPS}, 'README.md'),
    ({'spec': STEPS.replace('Comma', 'Tab')}, 'docs/specs/0001-exam-bank-skill.md'),
    ({'server': ['Import into the sheet:']}, 'app/server/server.js'),
])
def test_import_steps_drift_names_the_copy(docs, change, culprit):
    write_import_steps(docs, **change)
    failures = check_docs(docs)
    assert failures and failures[0].startswith(culprit)
