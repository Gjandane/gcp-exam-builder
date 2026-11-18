import json
import os
import shutil
import subprocess
import sys

import yaml

from conftest import FIXTURES, SCRIPTS, SKILL


def state(root, env=None):
    return subprocess.run([sys.executable, str(SCRIPTS / 'eb.py'), 'state', 'pmle'],
                          cwd=root, capture_output=True, text=True, encoding='utf-8', env=env)


def prepare(root):
    shutil.copy(SKILL / 'templates/models.example.yaml', root / 'exam-bank/config/models.yaml')
    config = root / 'exam-bank/config/exams/pmle.yaml'
    config.write_text(config.read_text(encoding='utf-8').replace('enabled: true', 'enabled: false'), encoding='utf-8')
    folder = root / 'exam-bank/pmle'
    (folder / 'state.json').write_text('{"setup":{"passed_at":"2026-01-01T00:00:00Z"}}', encoding='utf-8')
    return folder


def test_export_metadata_format_difference_is_stale(root):
    folder = prepare(root)
    export = folder / 'export'
    export.mkdir()
    shutil.copy(FIXTURES / 'export/bank.jsonl', folder / 'bank.jsonl')
    shutil.copy(FIXTURES / 'export/pmle-questions.csv', export / 'pmle-questions.csv')
    meta = json.loads((FIXTURES / 'export/bank_meta.json').read_text(encoding='utf-8'))
    (folder / 'bank_meta.json').write_text(json.dumps(meta), encoding='utf-8')
    result = state(root)
    assert result.returncode == 0, result.stderr
    assert 'pending: bank changed since last export (0 rows differ)' in result.stdout


def test_source_table_lists_given_and_created_sources(root):
    folder = prepare(root)
    sources = folder / 'sources'
    sources.mkdir()
    (sources / 'given.jsonl').write_text('{"question":"one"}\n', encoding='utf-8')
    (sources / 'created.jsonl').write_text('{"question":"two"}\n', encoding='utf-8')
    result = state(root)
    assert result.returncode == 0, result.stderr
    assert '| given | given |' in result.stdout
    assert '| created | created |' in result.stdout


def test_failed_llm_page_counts_as_done_and_is_listed(root):
    folder = prepare(root)
    config_path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['llm_sources'] = [{'name': 'sample', 'enabled': True,
                              'urls': ['https://example.com/one']}]
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    raw = folder / 'raw/sample'
    raw.mkdir(parents=True)
    (raw / '01.meta.json').write_text('{"status":"failed: robots"}', encoding='utf-8')
    result = state(root)
    assert result.returncode == 0, result.stderr
    assert '- llm-scrape: done' in result.stdout
    assert '| sample 01 | llm-scrape | failed: robots |' in result.stdout


def test_llm_fetch_without_result_is_not_done(root):
    folder = prepare(root)
    config_path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['llm_sources'] = [{'name': 'sample', 'enabled': True,
                              'urls': ['https://example.com/one']}]
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    raw = folder / 'raw/sample'
    raw.mkdir(parents=True)
    (raw / '01.meta.json').write_text('{"status":"ok"}', encoding='utf-8')
    (raw / '01.txt').write_text('Fetched text', encoding='utf-8')
    result = state(root)
    assert result.returncode == 0, result.stderr
    assert '- llm-scrape: pending' in result.stdout


def test_malformed_llm_result_keeps_page_pending(root):
    folder = prepare(root)
    config_path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['llm_sources'] = [{'name': 'sample', 'enabled': True,
                              'urls': ['https://example.com/one']}]
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    batches = folder / 'batches/llm-scrape'
    batches.mkdir(parents=True)
    (batches / 'manifest.json').write_text('[{"batch_id":"llm-scrape-0001"}]', encoding='utf-8')
    (batches / 'llm-scrape-0001.in.json').write_text('{"source":"sample","url":"https://example.com/one"}', encoding='utf-8')
    (batches / 'llm-scrape-0001.json').write_text('{broken', encoding='utf-8')
    result = state(root)
    assert result.returncode == 0, result.stderr
    assert '- llm-scrape: pending' in result.stdout


def test_source_gate_keeps_scrape_waiting(root):
    folder = prepare(root)
    config_path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['curated_sites'][0]['enabled'] = True
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    (folder / 'state.json').write_text(json.dumps({'setup': {'passed_at': '2026-01-01T00:00:00Z'},
                                                  'gates': {'examtopics': 'Log in'}}), encoding='utf-8')
    sources = folder / 'sources'
    sources.mkdir()
    (sources / 'examtopics.progress.json').write_text('{"pages_done":1,"pages_total":1}', encoding='utf-8')
    result = state(root)
    assert result.returncode == 0, result.stderr
    assert '- scrape: waiting on user' in result.stdout
    assert '| examtopics | curated | waiting on user: Log in |' in result.stdout


def test_environment_override_preserves_source_statuses(root):
    prepare(root)
    config_path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['curated_sites'][0]['enabled'] = True
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    env = os.environ.copy()
    env['CLAUDE_CODE_EFFORT_LEVEL'] = 'high'
    result = state(root, env)
    assert result.returncode == 0, result.stderr
    assert 'Current step: setup' in result.stdout
    assert '- scrape: pending' in result.stdout
    assert '| examtopics | curated | pending |' in result.stdout


def test_invalid_models_preserves_source_statuses(root):
    prepare(root)
    config_path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['curated_sites'][0]['enabled'] = True
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    (root / 'exam-bank/config/models.yaml').write_text('invalid: true', encoding='utf-8')
    result = state(root)
    assert result.returncode == 0, result.stderr
    assert 'Current step: setup' in result.stdout
    assert '- scrape: pending' in result.stdout
    assert '| examtopics | curated | pending |' in result.stdout
