import os
import shutil
import subprocess
import sys

import pytest
import yaml

from conftest import SCRIPTS, SKILL


def call(root, *args, env=None):
    return subprocess.run([sys.executable, str(SCRIPTS / 'eb.py'), *args], cwd=root,
                          capture_output=True, text=True, encoding='utf-8', env=env)


def test_setup_stops_on_override_after_validating_config(root):
    shutil.copy(SKILL / 'templates/models.example.yaml', root / 'exam-bank/config/models.yaml')
    env = os.environ.copy()
    env['CLAUDE_CODE_EFFORT_LEVEL'] = 'high'
    result = call(root, 'setup', 'pmle', env=env)
    assert result.returncode == 1
    assert 'CLAUDE_CODE_EFFORT_LEVEL' in result.stderr


def test_state_routes_given_file_to_intake(root):
    shutil.copy(SKILL / 'templates/models.example.yaml', root / 'exam-bank/config/models.yaml')
    config = root / 'exam-bank/config/exams/pmle.yaml'
    config.write_text(config.read_text(encoding='utf-8').replace('enabled: true', 'enabled: false'), encoding='utf-8')
    folder = root / 'exam-bank/pmle'
    (folder / 'state.json').write_text('{"setup":{"passed_at":"2026-01-01T00:00:00Z"}}', encoding='utf-8')
    (folder / 'given/mine.md').write_text('## g-1\n', encoding='utf-8')
    result = call(root, 'state', 'pmle')
    assert result.returncode == 0, result.stderr
    assert 'Current step: intake' in result.stdout
    assert 'steps/04-intake.md' in result.stdout


def test_state_counts_changed_export_rows(root):
    shutil.copy(SKILL / 'templates/models.example.yaml', root / 'exam-bank/config/models.yaml')
    folder = root / 'exam-bank/pmle'
    given = folder / 'given/mine.md'
    given.write_text('## g-1\nSubdomain: 2.1\n\nFirst question?\n\n- [x] Yes\n  Why: Correct.\n- [ ] No\n  Why: Incorrect.\n', encoding='utf-8')
    for command in ('intake', 'merge', 'export'):
        result = call(root, command, 'pmle')
        assert result.returncode == 0, result.stderr
    given.write_text(given.read_text(encoding='utf-8').replace('First question?', 'Changed question?'), encoding='utf-8')
    for command in ('intake', 'merge'):
        result = call(root, command, 'pmle')
        assert result.returncode == 0, result.stderr
    result = call(root, 'state', 'pmle')
    assert 'pending: bank changed since last export (1 rows differ)' in result.stdout


@pytest.mark.parametrize('change', ['duplicate_source', 'numeric_subdomain', 'bad_slug'])
def test_setup_rejects_invalid_exam_config(root, change):
    shutil.copy(SKILL / 'templates/models.example.yaml', root / 'exam-bank/config/models.yaml')
    path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(path.read_text(encoding='utf-8'))
    if change == 'duplicate_source':
        config['llm_sources'][0]['name'] = config['curated_sites'][0]['name']
    elif change == 'numeric_subdomain':
        config['sections'][0]['subdomains'][0]['number'] = 1.1
    else:
        config['slug'] = 'wrong'
    path.write_text(yaml.safe_dump(config), encoding='utf-8')
    result = call(root, 'setup', 'pmle')
    assert result.returncode == 1
    assert 'Invalid config' in result.stderr


def test_unknown_forced_step_lists_valid_names(root):
    result = call(root, 'state', 'pmle', 'nonesuch')
    assert result.returncode == 1
    assert 'setup' in result.stderr and 'export' in result.stderr
