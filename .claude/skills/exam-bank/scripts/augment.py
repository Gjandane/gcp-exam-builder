"""Step 9: opt-in augment. Gap plan, create Batches, blind verify Batches, keep or drop."""
import json
import math
import pathlib
import random
from fractions import Fraction

import batches
import merge
import setup
import store
import validate

STEP = 'augment'
LETTERS = 'ABCDEF'
LEVEL = {'low': 0, 'medium': 1, 'high': 2}
MAX_EXAMPLES = 5
KIND_TASK = {'create': 'augmentation', 'verify': 'answer_filling'}
KIND_WORKER = {'create': 'augment', 'verify': 'answers'}


# Gap rule

def targets(config, settings):
    """Target per Subdomain: weighted share of target_total, nearest integer, not under the floor."""
    sections = config['sections']
    total = sum(Fraction(str(s['weight'])) for s in sections)
    result = {}
    for section in sections:
        subs = section['subdomains']
        raw = (settings['target_total'] * Fraction(str(section['weight'])) / total / len(subs)
               if total else Fraction(0))
        target = max(settings['min_per_subdomain'], math.floor(raw + Fraction(1, 2)))
        for sub in subs:
            result[sub['number']] = target
    return result


def scale(gaps, cap):
    """Scale gaps to the cap by largest remainder. Gaps at or under the cap stay as they are."""
    total = sum(gaps)
    if total <= cap:
        return list(gaps)
    shares = [gap * cap for gap in gaps]
    planned = [share // total for share in shares]
    spare = cap - sum(planned)
    order = sorted(range(len(gaps)), key=lambda i: (-(shares[i] % total), i))
    for i in order[:spare]:
        planned[i] += 1
    return planned


def gap_table(config, rows, settings):
    wanted = targets(config, settings)
    active = {}
    for row in rows:
        if row.get('status') == 'active':
            active[row.get('subdomain')] = active.get(row.get('subdomain'), 0) + 1
    entries = [{'subdomain': sub['number'], 'title': sub['title'], 'active': active.get(sub['number'], 0),
                'target': wanted[sub['number']]}
               for section in config['sections'] for sub in section['subdomains']]
    gaps = [max(0, entry['target'] - entry['active']) for entry in entries]
    for entry, gap, planned in zip(entries, gaps, scale(gaps, settings['max_created_per_run'])):
        entry.update(gap=gap, planned=planned)
    return entries


def table_text(entries, settings):
    lines = ['| Subdomain | Active rows | Target | Planned new |', '| --- | --- | --- | --- |']
    lines += [f'| {e["subdomain"]} | {e["active"]} | {e["target"]} | {e["planned"]} |' for e in entries]
    planned, gaps = sum(e['planned'] for e in entries), sum(e['gap'] for e in entries)
    lines.append(f'Total planned: {planned} of max_created_per_run {settings["max_created_per_run"]}'
                 f' (gaps total {gaps})')
    return '\n'.join(lines)


# Configuration

def load_models(root):
    import yaml
    return yaml.safe_load((root / 'exam-bank/config/models.yaml').read_text(encoding='utf-8'))


def kind_options(models):
    """Per kind: alias and effort of its task, and the Batch size and parallelism."""
    options = {kind: models['defaults'] | models['tasks'][task] for kind, task in KIND_TASK.items()}
    for value in options.values():
        value['max_parallel'] = min(value['max_parallel'], 20)
    return options


# Create inputs

def section_of(config, subdomain):
    for section in config['sections']:
        if any(sub['number'] == subdomain for sub in section['subdomains']):
            return {sub['number'] for sub in section['subdomains']}
    return {subdomain}


def scoped(rows, config, subdomain, keep):
    """Rows of the Subdomain, or of its Section when the Subdomain has none."""
    for scope in ({subdomain}, section_of(config, subdomain)):
        found = [row for row in rows if row.get('status') == 'active'
                 and row.get('subdomain') in scope and keep(row)]
        if found:
            return found
    return []


def pick_examples(rows, config, subdomain, batch_id):
    def usable(row):
        return (row.get('lineage') != 'created' and row.get('answer')
                and (row.get('answer_checked_at') or not row.get('uncertain')))
    pool = sorted(scoped(rows, config, subdomain, usable), key=lambda row: row['id'])
    sourced = [row for row in pool
               if any(c.get('explanation_by') == 'source' for c in row['choices'])]
    rest = [row for row in pool if row not in sourced]
    rng = random.Random(batch_id)
    rng.shuffle(sourced)
    rng.shuffle(rest)
    return (sourced + rest)[:MAX_EXAMPLES]


def create_input(entry, rows, config):
    item = entry['items'][0]
    subdomain = item['subdomain']
    titles = store.subdomain_titles(config)
    examples = [{'id': row['id'], 'question': row['question'],
                 'choices': [{'letter': c['letter'], 'text': c['text'], 'explanation': c.get('explanation', '')}
                             for c in row['choices']],
                 'answer': row['answer']}
                for row in pick_examples(rows, config, subdomain, entry['batch_id'])]
    stems = [row['question'] for row in rows
             if row.get('status') == 'active' and row.get('subdomain') == subdomain]
    sample = scoped(rows, config, subdomain, lambda row: True) or [
        row for row in rows if row.get('status') == 'active']
    mix = {}
    for row in sample:
        mix[len(row['choices'])] = mix.get(len(row['choices']), 0) + 1
    return {'batch_id': entry['batch_id'], 'step': STEP, 'kind': 'create',
            'subdomain': {'number': subdomain, 'title': titles[subdomain]}, 'count': item['count'],
            'examples': examples, 'existing_stems': stems,
            'choice_count_mix': {str(k): mix[k] for k in sorted(mix)},
            'multi_select_share': round(sum(len(r['answer']) > 1 for r in sample) / len(sample), 2) if sample else 0}


def verify_input(creator, item):
    """The created question without its answer and explanations, and nothing to read as a source."""
    return {'step': STEP, 'kind': 'verify',
            'questions': [{'id': item,
                           'question': creator['question'],
                           'choices': [{'letter': letter, 'text': choice['text']}
                                       for letter, choice in zip(LETTERS, creator['choices'])]}],
            'source_answers': {}}


# Manifest

def add_entry(folder, entries, kind, items, now, data, attempt=1, retry_of=None):
    sequence = max((int(e['batch_id'].rsplit('-', 1)[1]) for e in entries), default=0) + 1
    entry = {'batch_id': f'{STEP}-{sequence:04d}', 'kind': kind, 'items': items,
             'attempt': attempt, 'retry_of': retry_of, 'created_at': now}
    directory = folder / 'batches' / STEP
    data['batch_id'] = entry['batch_id']
    store.write_atomic(directory / f'{entry["batch_id"]}.in.json', store.dump_json(data))
    entries.append(entry)
    store.write_atomic(directory / 'manifest.json', store.dump_json(entries))
    return entry


def open_work(folder):
    _total, _done, pending, failed = batches.counts(folder, STEP)
    return pending + len(failed)


def plan(root, exam, now, answer=None):
    config = setup.check_config(root, exam)
    models = load_models(root)
    settings = models['augment']
    folder = store.exam_dir(root, exam)
    rows = store.read_jsonl(folder / 'bank.jsonl')
    entries_table = gap_table(config, rows, settings)
    data = store.read_json(folder / 'state.json', {})
    opt_in = data.get('augment', {}).get('opt_in')
    status = 'unset' if opt_in is None else 'yes' if opt_in else 'no'
    if answer is None:
        text = table_text(entries_table, settings) + f'\nopt_in: {status}'
        if open_work(folder):
            text += '\nA plan is open. Run dispatch to finish it. A new plan waits until it is done.'
        return text
    if answer not in ('yes', 'no'):
        raise store.Stop('augment-plan takes yes or no.')
    if answer == 'no':
        data['augment'] = {'opt_in': False, 'asked_at': now}
        store.write_atomic(folder / 'state.json', store.dump_json(data))
        return 'Augment skipped.'
    if open_work(folder):
        data['augment'] = {'opt_in': True, 'asked_at': now}
        store.write_atomic(folder / 'state.json', store.dump_json(data))
        return 'A plan is open already and stays fixed. Run dispatch to finish it.'
    size = kind_options(models)['create']['batch_size']
    entries = store.read_json(folder / 'batches' / STEP / 'manifest.json', [])
    created = 0
    for line in entries_table:
        remaining = line['planned']
        while remaining:
            count = min(size, remaining)
            entry = add_entry(folder, entries, 'create', [{'subdomain': line['subdomain'], 'count': count}],
                              now, {})
            # Inputs hold bank-derived examples, so write them once the id is known.
            store.write_atomic(folder / 'batches' / STEP / f'{entry["batch_id"]}.in.json',
                               store.dump_json(create_input(entry, rows, config)))
            remaining -= count
            created += 1
    data['augment'] = {'opt_in': True, 'asked_at': now}
    store.write_atomic(folder / 'state.json', store.dump_json(data))
    return (f'Plan written: {created} create Batches, {sum(e["planned"] for e in entries_table)} questions.')


# Dispatch

def publish(folder, entries, outcomes, options):
    max_parallel = min(value['max_parallel'] for value in options.values())
    pending = batches.dispatchable(folder, STEP, entries, outcomes)
    data = store.read_json(folder / 'state.json', {})
    data.setdefault('dispatch_waves', {})[STEP] = [e['batch_id'] for e in pending[:max_parallel]]
    store.write_atomic(folder / 'state.json', store.dump_json(data))
    lines = [f'max_parallel: {max_parallel}', 'dispatch:']
    if not pending:
        lines.append('[]')
    directory = folder / 'batches' / STEP
    skill = pathlib.Path(__file__).resolve().parents[1]
    for entry in pending:
        kind = entry['kind']
        lines.append(json.dumps({
            'batch_id': entry['batch_id'],
            'input_path': (directory / f'{entry["batch_id"]}.in.json').as_posix(),
            'result_path': (directory / f'{entry["batch_id"]}.json').as_posix(),
            'worker_file': (skill / 'workers' / f'{KIND_WORKER[kind]}.md').as_posix(),
            'subagent_type': 'exam-bank-researcher', 'alias': options[kind]['alias'],
            'effort': options[kind]['effort'],
        }, ensure_ascii=False))
    return '\n'.join(lines)


def retry(folder, entries, outcome, entry, rows, config, now, attempt):
    if entry['kind'] == 'create':
        item = {'subdomain': entry['items'][0]['subdomain'], 'count': outcome['need']}
        new = add_entry(folder, entries, 'create', [item], now, {}, attempt, entry['batch_id'])
        store.write_atomic(folder / 'batches' / STEP / f'{new["batch_id"]}.in.json',
                           store.dump_json(create_input(new, rows, config)))
    else:
        old = store.read_json(folder / 'batches' / STEP / f'{entry["batch_id"]}.in.json', {})
        add_entry(folder, entries, 'verify', entry['items'], now, old, attempt, entry['batch_id'])


def ensure_retries(folder, entries, outcomes, rows, config, now, restart=False):
    """Requeue a rejected entry once. With restart, an exhausted entry starts over at attempt 1."""
    superseded = {e.get('retry_of') for e in entries}
    for entry in list(entries):
        outcome = outcomes.get(entry['batch_id'])
        if not outcome or not outcome['rejected'] or entry['batch_id'] in superseded:
            continue
        if entry['attempt'] >= 3:
            if restart:
                retry(folder, entries, outcome, entry, rows, config, now, 1)
        else:
            retry(folder, entries, outcome, entry, rows, config, now, entry['attempt'] + 1)


def run(root, exam, now):
    config = setup.check_config(root, exam)
    options = kind_options(load_models(root))
    folder = store.exam_dir(root, exam)
    entries = store.read_json(folder / 'batches' / STEP / 'manifest.json', [])
    outcomes = store.read_json(folder / 'state.json', {}).get('dispatch', {}).get(STEP, {})
    rows = store.read_jsonl(folder / 'bank.jsonl')
    ensure_retries(folder, entries, outcomes, rows, config, now, restart=True)
    return publish(folder, entries, outcomes, options)


# Validation

def pseudo_row(question, choices):
    """The shape `validate.answers` reads, for a question that is not in the bank."""
    return {'question': question, 'answer': [], 'answer_by': '', 'sources': [],
            'choices': [{'letter': letter, 'text': text, 'explanation': '', 'explanation_by': ''}
                        for letter, text in zip(LETTERS, choices)]}


def check_create(item, data):
    if item.get('status') == 'unusable':
        reason = item.get('reason')
        return '' if isinstance(reason, str) and reason.strip() else 'unusable needs a reason.'
    if item.get('status') != 'ok':
        return 'Unknown question status.'
    question, choices = item.get('question'), item.get('choices')
    if not isinstance(question, str) or not question.strip() or not validate.cell_text(question):
        return 'Invalid question text.'
    if (not isinstance(choices, list) or not 2 <= len(choices) <= 6
            or any(not isinstance(c, dict) or not isinstance(c.get('text'), str) or not c['text'].strip()
                   or not validate.cell_text(c['text']) or not isinstance(c.get('explanation'), str)
                   for c in choices)):
        return 'A question needs 2 to 6 valid choices.'
    if item.get('subdomain') != data['subdomain']['number']:
        return 'Subdomain does not match the Batch.'
    derived = item.get('derived_from')
    known = {example['id'] for example in data['examples']}
    if (not isinstance(derived, list) or any(not isinstance(x, str) or x not in known for x in derived)
            or (known and not derived) or len(set(derived)) != len(derived)):
        return 'derived_from must list example IDs from the input.'
    refs = item.get('refs')
    if not isinstance(refs, list) or not refs:
        return 'At least one documentation reference is required.'
    shaped = {'status': 'ok', 'answer': item.get('answer'), 'confidence': item.get('confidence'),
              'note': item.get('note'), 'refs': refs,
              'explanations': {letter: c['explanation'] for letter, c in zip(LETTERS, choices)},
              'why_conflicts': []}
    return validate.answers(shaped, pseudo_row(question, [c['text'] for c in choices]))


def create_outcome(entry, parsed, result, error, data):
    count = entry['items'][0]['count']
    outcome = {'accepted': [], 'rejected': {}, 'unusable': {}, 'parsed': parsed, 'need': count}
    if error:
        outcome['rejected'] = {'*': error}
        return outcome
    seen = {}
    for item in result['results']:
        if isinstance(item, dict) and isinstance(item.get('key'), str) and item['key']:
            seen.setdefault(item['key'], []).append(item)
    for key, items in seen.items():
        if len(outcome['accepted']) + len(outcome['unusable']) >= count:
            break
        reason = 'Duplicate question key.' if len(items) > 1 else check_create(items[0], data)
        if reason:
            outcome['rejected'][key] = reason
        elif items[0]['status'] == 'unusable':
            outcome['unusable'][key] = items[0]['reason']
        else:
            outcome['accepted'].append(key)
    outcome['need'] = count - len(outcome['accepted']) - len(outcome['unusable'])
    if outcome['need'] and not outcome['rejected']:
        outcome['rejected'] = {'*': 'Missing question results.'}
    elif not outcome['need']:
        outcome['rejected'] = {}
    return outcome


# Keep or drop

def decide(creator, verify):
    """Return the kept confidence and an empty reason, or None and the drop reason."""
    if verify.get('status') == 'unusable':
        return None, 'Verify session found the question unusable: ' + verify['reason']
    if sorted(verify['answer']) != sorted(creator['answer']):
        return None, 'Verify answer differs from the creator answer.'
    if verify['confidence'] == 'low':
        return None, 'Verify confidence is low.'
    return min(creator['confidence'], verify['confidence'], key=LEVEL.get), ''


def created_record(exam, creator, verify, ref, key, confidence, now):
    answer = sorted(creator['answer'])
    refs = list(dict.fromkeys(creator['refs'] + verify.get('refs', [])))
    choices = [{'letter': letter, 'text': c['text'], 'explanation': c['explanation'], 'explanation_by': 'llm'}
               for letter, c in zip(LETTERS, creator['choices'])]
    return {'exam': exam, 'status': 'active', 'subdomain': creator['subdomain'], 'subdomain_by': 'llm',
            'subdomain_confidence': '', 'question': creator['question'], 'choices': choices,
            'answer': answer, 'answer_by': 'llm', 'answer_confidence': confidence,
            'answer_note': creator['note'], 'answer_refs': refs, 'answer_checked_at': now,
            'explanation_by': 'llm', 'lineage': 'created', 'uncertain': False,
            'derived_from': list(creator['derived_from']), 'updated_at': now,
            'rechecked_at': '', 'recheck_note': '',
            'sources': [{'name': 'created', 'url': f'batches/augment/{ref.split("#", 1)[0]}.json#{key}',
                         'source_question_no': key, 'site_answer': answer,
                         'community_answer': [], 'scraped_at': now, 'subdomain_label': '',
                         'explanation_block': '', 'unsure': False}]}


def creator_item(folder, ref):
    batch_id, key = ref.split('#', 1)
    result = store.read_json(folder / 'batches' / STEP / f'{batch_id}.json', {})
    for item in result.get('results', []):
        if isinstance(item, dict) and item.get('key') == key and item.get('status') == 'ok':
            return item
    return None


def merge_created(folder, config, data, now):
    """Run merge on the created file only. Other source files stay as they are."""
    rows = store.read_jsonl(folder / 'bank.jsonl')
    before = store.dump_jsonl(rows)
    path = folder / 'sources/created.jsonl'
    _new, events = merge.merge_records(rows, [('created', store.read_jsonl(path))], now, config,
                                       data.get('given_texts', {}))
    if store.dump_jsonl(rows) != before:
        store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    data.setdefault('merged', {})['sources/created.jsonl'] = store.sha256_file(path)
    return [e for e in events if e['kind'] != 'missing_key']


def apply(root, exam, now):
    config = setup.check_config(root, exam)
    options = kind_options(load_models(root))
    folder = store.exam_dir(root, exam)
    directory = folder / 'batches' / STEP
    entries = store.read_json(directory / 'manifest.json', [])
    data = store.read_json(folder / 'state.json', {})
    outcomes = data.setdefault('dispatch', {}).setdefault(STEP, {})
    rows = store.read_jsonl(folder / 'bank.jsonl')
    ensure_retries(folder, entries, outcomes, rows, config, now)
    pending = batches.unsettled(entries, outcomes)
    max_parallel = min(value['max_parallel'] for value in options.values())
    wave = set(data.get('dispatch_waves', {}).get(STEP, [e['batch_id'] for e in pending[:max_parallel]]))
    events, records = [], []
    for entry in pending:
        path = directory / f'{entry["batch_id"]}.json'
        if entry['batch_id'] not in wave and not path.exists():
            continue
        parsed, result, error = validate.result_file(path, entry, STEP)
        input_data = store.read_json(directory / f'{entry["batch_id"]}.in.json', {})
        if entry['kind'] == 'create':
            outcome = create_outcome(entry, parsed, result, error, input_data)
            for key in outcome['accepted']:
                ref = f'{entry["batch_id"]}#{key}'
                if not any(e['kind'] == 'verify' and e['items'] == [ref] for e in entries):
                    creator = next(i for i in result['results'] if i.get('key') == key)
                    add_entry(folder, entries, 'verify', [ref], now, verify_input(creator, ref))
            for key, reason in outcome['unusable'].items():
                events.append({'at': now, 'step': STEP, 'kind': 'dropped', 'source': 'created',
                               'ref': f'{entry["batch_id"]}#{key}', 'reason': 'Creator found the question unusable: ' + reason})
        else:
            outcome = verify_outcome(folder, entry, parsed, result, error, input_data, config, now, events, records)
        outcomes[entry['batch_id']] = outcome
    if records:
        path = folder / 'sources/created.jsonl'
        urls = {record['sources'][0]['url'] for record in records}
        kept = [r for r in store.read_jsonl(path) if r['sources'][0]['url'] not in urls]
        store.write_atomic(path, store.dump_jsonl(kept + records))
    if records or (folder / 'sources/created.jsonl').is_file():
        events += merge_created(folder, config, data, now)
    recorded = {(e['step'], e['kind'], e['ref'], e['reason']) for e in store.read_jsonl(folder / 'log.jsonl')}
    store.append_log(root, exam, [e for e in events
                                  if (e['step'], e['kind'], e['ref'], e['reason']) not in recorded])
    store.write_atomic(folder / 'state.json', store.dump_json(data))
    ensure_retries(folder, entries, outcomes, rows, config, now)
    total, done, pending_count, failed = batches.counts(folder, STEP)
    kept_count = sum(1 for o in outcomes.values() if o.get('kept'))
    dropped = sum(1 for o in outcomes.values() if o.get('kept') is False) + sum(
        len(o.get('unusable', {})) for o in outcomes.values())
    return (publish(folder, entries, outcomes, options)
            + f'\nBatches: total {total}, done {done}, pending {pending_count}, failed {len(failed)}'
            + (f' ({", ".join(failed)})' if failed else '')
            + f'\nQuestions: kept {kept_count}, dropped {dropped}')


def verify_outcome(folder, entry, parsed, result, error, input_data, config, now, events, records):
    ref = entry['items'][0]
    question = input_data['questions'][0] if input_data.get('questions') else {'question': '', 'choices': []}
    row = pseudo_row(question['question'], [c['text'] for c in question['choices']])
    accepted, rejected = validate.questions(entry, result, error, lambda value, _cfg: validate.answers(value, row), config)
    outcome = {'accepted': list(accepted), 'rejected': rejected, 'parsed': parsed}
    if ref in accepted:
        creator = creator_item(folder, ref)
        verify = accepted[ref]
        if creator is None:
            confidence, reason = None, 'Creator result is missing.'
        else:
            confidence, reason = decide(creator, verify)
        outcome['kept'] = confidence is not None
        if confidence is None:
            events.append({'at': now, 'step': STEP, 'kind': 'dropped', 'source': 'created',
                           'ref': ref, 'reason': reason})
        else:
            records.append(created_record(config['slug'], creator, verify, ref, ref.split('#', 1)[1],
                                          confidence, now))
    return outcome
