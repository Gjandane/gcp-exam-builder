"""Plan, validate and index one Study guide chapter outside shared dispatch."""
import datetime
import html
import random
import re

import yaml

import batches
import ids
import store
import validate

HEADINGS = ('Scope', 'Key concepts', 'Decision table', 'Traps', 'Question map', 'References')
SKILL = '.claude/skills/exam-bank'


def chapter_path(folder, subdomain, title):
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return folder / 'study-guide' / f'{subdomain}-{slug}.md'


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
    if not match:
        raise ValueError('Missing YAML front matter.')
    metadata = yaml.safe_load(match[1])
    if not isinstance(metadata, dict):
        raise ValueError('Front matter must be a mapping.')
    return metadata, text[match.end():]


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('written_at must be a UTC timestamp.')
    return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')


def load_input(path):
    try:
        return store.read_json(path, {})
    except (ValueError, OSError):
        return {}


def rebuild(root, exam, config, rows, now):
    """The single writer of study_guide_state.md, used on every plan/check."""
    folder = store.exam_dir(root, exam)
    active = [row for row in rows if row.get('status') == 'active']
    untagged = sum(not row.get('subdomain') for row in active)
    entries = []
    for subdomain, title in store.subdomain_titles(config).items():
        questions = [row for row in active if row.get('subdomain') == subdomain]
        path = chapter_path(folder, subdomain, title)
        inp = load_input(folder / 'batches/study-guide' / f'{subdomain}.in.json')
        reasons = []
        if untagged:
            reasons.append(f'{untagged} pending tag')
        answers = sum(batches.answers_pending(row) for row in questions)
        explanations = sum(not batches.answers_pending(row) and any(
            not choice.get('explanation') for choice in row['choices']) for row in questions)
        if answers:
            reasons.append(f'{answers} pending answers')
        if explanations:
            reasons.append(f'{explanations} pending explanations')
        if not questions and not path.is_file():
            reasons.append('no active questions')
        status = 'blocked: ' + ', '.join(reasons) if reasons else 'ready'
        written = ''
        if not reasons and path.is_file():
            try:
                meta, _ = frontmatter(path)
                timestamp(meta.get('written_at'))
                written = meta['written_at']
                old = inp.get('active_ids', [])
                current = [row['id'] for row in questions]
                changed = len(set(old) ^ set(current)) + sum(
                    row['id'] in old and row.get('updated_at', '') > written for row in questions)
                status = (f'stale: {changed} changed' if old != current or changed else
                          f'done {written[:10]}')
                if status.startswith('done') and (not inp or chapter_error(path, inp, config, now)):
                    status = 'stale: invalid chapter'
            except (ValueError, yaml.YAMLError, OSError, TypeError, KeyError):
                status = 'stale: invalid front matter'
        entries.append(dict(subdomain=subdomain, title=title, questions=questions,
                            status=status, path=path, input=inp))
    done = sum(entry['status'].startswith('done') for entry in entries)
    lines = [f'# Study guide: {exam} (guide {config["guide_version"]}), '
             f'{done} of {len(entries)} chapters done', '']
    for entry in entries:
        total = len(entry['questions'])
        fed = min(total, len(entry['input']['questions'])) if entry['input'].get('questions') else total
        count = f'{fed} of {total} Qs' if fed < total else f'{total} Qs'
        status = entry['status']
        redo = ' redo' if entry['path'].exists() else ''
        command = f'/exam-bank {exam} study-guide {entry["subdomain"]}{redo}'
        lines.append(f'- [{"x" if status.startswith("done") else " "}] '
                     f'{entry["subdomain"]} {entry["title"]} | {count} | {status} | `{command}`')
    store.write_atomic(folder / 'study_guide_state.md', ('\n'.join(lines) + '\n').encode('utf-8'))
    return entries


def plan(root, exam, now, subdomain=None, redo=False):
    config = store.load_exam_config(root, exam)
    folder = store.exam_dir(root, exam)
    entries = rebuild(root, exam, config, store.read_jsonl(folder / 'bank.jsonl'), now)
    if subdomain is None:
        entry = next((item for item in entries if item['status'] == 'ready'), None)
        if entry is None:
            raise store.Stop('No ready Subdomain. See study_guide_state.md.')
    else:
        entry = next((item for item in entries if item['subdomain'] == subdomain), None)
        if entry is None:
            raise store.Stop(f'Unknown Subdomain: {subdomain}.')
    subdomain = entry['subdomain']
    if entry['status'].startswith('blocked'):
        raise store.Stop(f'{subdomain}: {entry["status"]}')
    if entry['path'].exists() and not redo:
        raise store.Stop(f'{subdomain} already has a chapter. Run /exam-bank {exam} study-guide {subdomain} redo.')
    models_path = root / 'exam-bank/config/models.yaml'
    try:
        models = yaml.safe_load(models_path.read_text(encoding='utf-8'))
        task = models['tasks']['study_guide_chapter']
        cap = models['study_guide']['max_questions']
        if type(cap) is not int or cap < 1:
            raise ValueError('study_guide.max_questions must be positive to write a chapter')
        model, effort = task['alias'], task['effort']
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        raise store.Stop(f'Invalid Study guide config: {error}.') from error
    questions = entry['questions']
    fed = questions
    if len(questions) > cap:
        rng = random.Random(f'{exam}:{subdomain}')
        ordinary = [row for row in questions if row.get('lineage') != 'created']
        created = [row for row in questions if row.get('lineage') == 'created']
        rng.shuffle(ordinary)
        rng.shuffle(created)
        fed = (ordinary + created)[:cap]
    inp = dict(exam=exam, subdomain=subdomain, title=entry['title'],
               guide_version=str(config['guide_version']), active_ids=[row['id'] for row in questions],
               questions=[dict(row, marked=bool(row.get('uncertain') or any(
                   row.get(field) == 'low' for field in ('answer_confidence', 'subdomain_confidence'))))
                          for row in fed],
               chapter_path=entry['path'].relative_to(root).as_posix(), model=model,
               written_at=now)
    input_path = folder / 'batches/study-guide' / f'{subdomain}.in.json'
    # Keep a completed chapter's input intact until redo has been requested.
    if redo:
        entry['path'].unlink(missing_ok=True)
    store.write_atomic(input_path, store.dump_json(inp))
    rebuild(root, exam, config, store.read_jsonl(folder / 'bank.jsonl'), now)
    return (f'Subdomain: {subdomain} {entry["title"]}\nInput: {input_path.relative_to(root).as_posix()}\n'
            f'Chapter: {inp["chapter_path"]}\nWorker: {SKILL}/workers/study-guide.md\n'
            f'Agent type: exam-bank-researcher\nAlias: {model}\nEffort: {effort}\n'
            f'Questions: {len(fed)} of {len(questions)}\n'
            f'Check: python {SKILL}/scripts/eb.py study-guide-check {exam} {subdomain}')


def chapter_error(path, inp, config, now):
    try:
        meta, body = frontmatter(path)
        fed_ids = [row['id'] for row in inp['questions']]
        for field in ('exam', 'subdomain', 'title', 'guide_version', 'model'):
            if not isinstance(meta.get(field), str) or meta[field] != inp[field]:
                return f'Wrong front matter: {field}.'
        if meta.get('question_ids') != fed_ids:
            return 'Wrong front matter: question_ids must match the fed IDs.'
        if meta.get('guide_version') != str(config['guide_version']):
            return 'Wrong front matter: guide_version.'
        written = timestamp(meta.get('written_at'))
        if written > timestamp(now) or written < timestamp(inp['written_at']):
            return 'Wrong front matter: written_at is outside this run.'
    except (ValueError, yaml.YAMLError, KeyError, TypeError) as error:
        return f'Invalid front matter: {error}'
    headings = re.findall(r'^##\s+(.+?)\s*#*\s*$', body, re.M)
    if headings != list(HEADINGS):
        return 'Headings must be Scope, Key concepts, Decision table, Traps, Question map, References, in order.'
    if any(qid not in fed_ids for qid in re.findall(r'\bq_[a-zA-Z0-9_]+\b', body)):
        return 'Cited ID not in the input.'
    if not validate.doc_links(body):
        return 'URL fails the doc host rule.'
    # Check Markdown destinations as well, including relative and non-HTTPS links.
    destinations = re.findall(r'\]\(\s*<?([^\s)>]+)', body)
    destinations += re.findall(r'^\s*\[[^\]]+\]:\s*<?([^\s>]+)', body, re.M)
    destinations += re.findall(r'<([a-z][a-z0-9+.-]*:[^\s>]+|//[^\s>]+)>', body, re.I)
    for quoted_double, quoted_single, unquoted in re.findall(
            r'\b(?:href|src)\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27|([^\s>]+))',
            body, re.I):
        destinations.append(html.unescape(quoted_double or quoted_single or unquoted))
    if any(not validate.doc_host(url) for url in destinations):
        return 'URL fails the doc host rule.'
    count = len(body.split())
    if not 1200 <= count <= 3500:
        return f'Chapter length {count} words is outside 1200 to 3500.'
    words = ids.norm(body).split()
    runs = {tuple(words[i:i + 12]) for i in range(len(words) - 11)}
    for row in inp['questions']:
        for text in [row['question'], *(choice['text'] for choice in row['choices'])]:
            original = ids.norm(text).split()
            if any(tuple(original[i:i + 12]) in runs for i in range(len(original) - 11)):
                return 'Copied run of 12 words from an input stem or choice.'
    return ''


def check(root, exam, now, subdomain):
    config = store.load_exam_config(root, exam)
    folder = store.exam_dir(root, exam)
    entries = rebuild(root, exam, config, store.read_jsonl(folder / 'bank.jsonl'), now)
    entry = next((item for item in entries if item['subdomain'] == subdomain), None)
    if entry is None:
        raise store.Stop(f'Unknown Subdomain: {subdomain}.')
    path = entry['path']
    inp = entry['input']
    if not path.is_file():
        raise store.Stop(f'Missing chapter: {path.as_posix()}')
    error = (chapter_error(path, inp, config, now) if inp else 'Missing chapter input.')
    if error:
        path.unlink()
    entries = rebuild(root, exam, config, store.read_jsonl(folder / 'bank.jsonl'), now)
    if error:
        raise store.Stop(f'{subdomain}: {error} Invalid chapter deleted.')
    status = next(item['status'] for item in entries if item['subdomain'] == subdomain)
    return f'{subdomain}: check passed; {status}.'
