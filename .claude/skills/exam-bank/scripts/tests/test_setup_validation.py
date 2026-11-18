"""Setup rejects invalid config before inspecting the environment or tools."""
import os
import shutil
import subprocess
import sys

import pytest
import yaml

from conftest import SCRIPTS, SKILL


@pytest.mark.parametrize('change', [
    'bad_tasks_type', 'missing_default', 'duplicate_subdomain', 'bad_hint',
    'reserved_source', 'uppercase_source', 'bad_enabled', 'bad_trust',
    'missing_augment', 'negative_augment', 'missing_study_guide', 'bad_section_number',
])
def test_setup_rejects_invalid_config_with_a_fix(root, change):
    models_path = root / 'exam-bank/config/models.yaml'
    exam_path = root / 'exam-bank/config/exams/pmle.yaml'
    shutil.copy(SKILL / 'templates/models.example.yaml', models_path)
    models = yaml.safe_load(models_path.read_text(encoding='utf-8'))
    exam = yaml.safe_load(exam_path.read_text(encoding='utf-8'))
    if change == 'bad_tasks_type':
        models['tasks'] = []
    elif change == 'missing_default':
        del models['defaults']['batch_size']
    elif change == 'duplicate_subdomain':
        exam['sections'][0]['subdomains'].append(exam['sections'][0]['subdomains'][0])
    elif change == 'bad_hint':
        exam['sections'][0]['subdomains'][0]['hint'] = 7
    elif change == 'reserved_source':
        exam['curated_sites'][0]['name'] = 'given'
    elif change == 'uppercase_source':
        exam['curated_sites'][0]['name'] = 'ExamTopics'
    elif change == 'bad_enabled':
        exam['curated_sites'][0]['enabled'] = 'false'
    elif change == 'missing_augment':
        del models['augment']['target_total']
    elif change == 'negative_augment':
        models['augment']['max_created_per_run'] = -1
    elif change == 'missing_study_guide':
        del models['study_guide']['max_questions']
    elif change == 'bad_section_number':
        del exam['sections'][0]['number']
        exam['sections'][0]['subdomains'] = []
    else:
        exam['llm_sources'][0]['answers_trusted'] = 'false'
    models_path.write_text(yaml.safe_dump(models), encoding='utf-8')
    exam_path.write_text(yaml.safe_dump(exam), encoding='utf-8')
    env = os.environ.copy()
    env['CLAUDE_CODE_EFFORT_LEVEL'] = 'high'
    result = subprocess.run([sys.executable, str(SCRIPTS / 'eb.py'), 'setup', 'pmle'],
                            cwd=root, env=env, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 1
    assert 'Invalid config' in result.stderr
    assert 'Fix the YAML files' in result.stderr
    assert 'Traceback' not in result.stderr


def test_setup_accepts_omitted_answer_trust_and_weights_over_100(root):
    models_path = root / 'exam-bank/config/models.yaml'
    exam_path = root / 'exam-bank/config/exams/pmle.yaml'
    shutil.copy(SKILL / 'templates/models.example.yaml', models_path)
    exam = yaml.safe_load(exam_path.read_text(encoding='utf-8'))
    for source in exam['curated_sites'] + exam['llm_sources']:
        source.pop('answers_trusted')
    exam_path.write_text(yaml.safe_dump(exam), encoding='utf-8')
    env = os.environ.copy()
    env['CLAUDE_CODE_EFFORT_LEVEL'] = 'high'
    result = subprocess.run([sys.executable, str(SCRIPTS / 'eb.py'), 'setup', 'pmle'],
                            cwd=root, env=env, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 1
    assert 'CLAUDE_CODE_EFFORT_LEVEL' in result.stderr
