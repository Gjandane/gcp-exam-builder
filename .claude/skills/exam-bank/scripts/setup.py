"""Validate configuration and prerequisites before building a bank."""
import importlib
import json
import os
import re
import subprocess
import sys

import store

TASKS = {'llm_scraping', 'subdomain_tagging', 'answer_filling', 'explanation_writing',
         'augmentation', 'report_recheck', 'study_guide_chapter'}
VARIABLES = ('CLAUDE_CODE_SUBAGENT_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL_FORCE',
             'CLAUDE_CODE_EFFORT_LEVEL')


def check_config(root, exam):
    base = root / 'exam-bank/config'
    paths = [base / 'models.yaml', base / 'exams' / f'{exam}.yaml']
    if not all(p.is_file() for p in paths):
        raise store.Stop('Missing config. Create exam-bank/config/exams, then run:\n'
                         'cp .claude/skills/exam-bank/templates/models.example.yaml exam-bank/config/models.yaml\n'
                         'cp .claude/skills/exam-bank/templates/exams/pmle.example.yaml '
                         f'exam-bank/config/exams/{exam}.yaml\n'
                         'PowerShell: use Copy-Item in place of cp.')
    try:
        import yaml
    except ImportError as error:
        raise store.Stop('Missing yaml. Run pip install -r requirements.txt.') from error
    try:
        models, config = [yaml.safe_load(p.read_text(encoding='utf-8')) for p in paths]
        if not isinstance(models, dict) or not isinstance(config, dict):
            raise ValueError('both configs must be mappings')
        if config.get('slug') != exam:
            raise ValueError(f'exam slug must equal {exam}')
        if not isinstance(models.get('tasks'), dict) or set(models['tasks']) != TASKS:
            raise ValueError('models tasks must contain exactly the seven configured tasks')
        defaults = models.get('defaults')
        if not isinstance(defaults, dict) or not {'batch_size', 'max_parallel'} <= defaults.keys():
            raise ValueError('defaults must include batch_size and max_parallel')
        for task in models['tasks'].values():
            if not isinstance(task, dict):
                raise ValueError('each task must be a mapping')
            if task['alias'] not in {'opus', 'sonnet', 'haiku', 'fable'} or task['effort'] not in {'low', 'medium', 'high', 'xhigh', 'max'}:
                raise ValueError('invalid model alias or effort')
        for opts in [defaults, *models['tasks'].values()]:
            for key in ('batch_size', 'max_parallel'):
                if key in opts and (type(opts[key]) is not int or opts[key] < 1):
                    raise ValueError(f'{key} must be a positive integer')
        for group, keys in (
            ('augment', ('target_total', 'min_per_subdomain', 'max_created_per_run')),
            ('study_guide', ('max_questions',)),
        ):
            settings = models.get(group)
            if not isinstance(settings, dict):
                raise ValueError(f'{group} must be a mapping')
            for key in keys:
                if type(settings.get(key)) is not int or settings[key] < 0:
                    raise ValueError(f'{group}.{key} must be a nonnegative integer')
        if not isinstance(config.get('name'), str) or not config['name'].strip():
            raise ValueError('exam name must be a nonempty string')
        if not isinstance(config.get('guide_version'), str) or not config['guide_version']:
            raise ValueError('guide_version must be a string')
        if not isinstance(config.get('sections'), list) or not config['sections']:
            raise ValueError('sections must be a nonempty list')
        seen = set()
        for section in config['sections']:
            if not isinstance(section, dict) or not isinstance(section.get('subdomains'), list):
                raise ValueError('each section needs a subdomains list')
            number = section.get('number')
            if not ((type(number) is int and number > 0) or
                    (isinstance(number, str) and number.isascii() and number.isdigit() and int(number) > 0)):
                raise ValueError('each section needs a positive integer number')
            if not section['subdomains']:
                raise ValueError('each section needs at least one subdomain')
            if not isinstance(section.get('title'), str) or type(section.get('weight')) not in (int, float):
                raise ValueError('each section needs a title and numeric weight')
            for sub in section['subdomains']:
                if not isinstance(sub, dict) or not isinstance(sub.get('title'), str):
                    raise ValueError('each subdomain needs a title')
                num = sub['number']
                if not isinstance(num, str) or not num.startswith(str(section['number']) + '.') or num in seen:
                    raise ValueError('subdomain numbers must be unique strings starting with their section number')
                if 'hint' in sub and not isinstance(sub['hint'], str):
                    raise ValueError('subdomain hint must be a string')
                seen.add(num)
        names = set()
        for key in ('curated_sites', 'llm_sources'):
            sources = config.get(key, [])
            if not isinstance(sources, list):
                raise ValueError(f'{key} must be a list')
            for source in sources:
                if not isinstance(source, dict):
                    raise ValueError(f'{key} entries must be mappings')
                name = source['name']
                if not isinstance(name, str) or not re.fullmatch('[a-z0-9-]+', name) or name in names or name in {'given', 'created'}:
                    raise ValueError('source names must be unique lowercase names, excluding given and created')
                names.add(name)
                if type(source.get('enabled')) is not bool:
                    raise ValueError(f'{name}: enabled must be true or false')
                if 'answers_trusted' in source and type(source['answers_trusted']) is not bool:
                    raise ValueError(f'{name}: answers_trusted must be true or false')
                if key == 'curated_sites' and (not isinstance(source.get('url'), str) or not source['url']):
                    raise ValueError(f'{name}: url must be a nonempty string')
                if key == 'llm_sources' and (not isinstance(source.get('urls'), list) or
                                             any(not isinstance(url, str) or not url for url in source['urls'])):
                    raise ValueError(f'{name}: urls must be a list of nonempty strings')
    except (ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as e:
        raise store.Stop(f'Invalid config: {e}. Fix the YAML files and rerun setup.') from e
    for name in VARIABLES:
        if name in os.environ:
            raise store.Stop(f'{name} is set. Unset {name} and rerun setup.')
    return config


def run(root, exam, now):
    check_config(root, exam)
    if sys.version_info < (3, 11):
        raise store.Stop('Python 3.11 or newer is required. Install it and rerun setup.')
    for name in ('requests', 'bs4', 'playwright', 'yaml'):
        try:
            importlib.import_module(name)
        except ImportError as e:
            raise store.Stop(f'Missing {name}. Run pip install -r requirements.txt.') from e
    probe = ('from playwright.sync_api import sync_playwright; '
             'from pathlib import Path; p=sync_playwright().start(); '
             'print(Path(p.chromium.executable_path).is_file()); p.stop()')
    try:
        result = subprocess.run([sys.executable, '-c', probe], capture_output=True,
                                text=True, timeout=15, check=True)
    except (subprocess.SubprocessError, OSError) as e:
        raise store.Stop('Could not check Playwright Chromium. Run playwright install chromium and rerun setup.') from e
    if result.stdout.strip() != 'True':
        raise store.Stop('Chromium missing. Run playwright install chromium.')
    folder = store.exam_dir(root, exam)
    for name in ('given', 'raw', 'sources', 'batches', 'reports', 'export', 'study-guide'):
        (folder / name).mkdir(parents=True, exist_ok=True)
    state = store.read_json(folder / 'state.json', {})
    state.setdefault('setup', {})['passed_at'] = now
    store.write_atomic(folder / 'state.json', store.dump_json(state))
    permissions = {'permissions': {'allow': [
        'Bash(python .claude/skills/exam-bank/scripts/eb.py *)',
        'Read(/.claude/skills/exam-bank/**)', 'Read(/exam-bank/**)',
        'Edit(/exam-bank/**)', 'WebSearch', 'WebFetch(domain:cloud.google.com)',
        'WebFetch(domain:docs.cloud.google.com)']}}
    return 'Setup passed. Merge this into .claude/settings.local.json:\n' + json.dumps(permissions, indent=2)
