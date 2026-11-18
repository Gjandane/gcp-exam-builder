"""Step 3: one Batch per saved page. Validation checks every text against the page."""

import fetch
import store
import validate
from ids import norm

STEP = 'llm-scrape'
LETTERS = 'ABCDEF'


def ref(source, number):
    return f'{source}/{number:02d}'


def split_ref(page_ref):
    source, number = page_ref.rsplit('/', 1)
    return source, int(number)


def page_meta(folder, page_ref):
    source, number = split_ref(page_ref)
    return fetch.meta_path(folder, source, number)


def page_files(folder, page_ref):
    source, number = split_ref(page_ref)
    return fetch.page_dir(folder, source) / f'{number:02d}.txt'


def has_valid_result(meta):
    return meta.get('status') == 'done-partial' or (meta.get('status') == 'ok' and meta.get('applied'))


# Forming Batches

def new_entry(folder, entries, page_ref, now, attempt=1, retry_of=None, only=None):
    sequence = max((int(e['batch_id'].rsplit('-', 1)[1]) for e in entries), default=0) + 1
    entry = {'batch_id': f'{STEP}-{sequence:04d}', 'kind': STEP, 'items': [page_ref],
             'attempt': attempt, 'retry_of': retry_of, 'created_at': now}
    source, _number = split_ref(page_ref)
    meta = store.read_json(page_meta(folder, page_ref), {})
    data = {'batch_id': entry['batch_id'], 'step': STEP, 'source': source, 'url': meta.get('url', ''),
            'txt_path': page_files(folder, page_ref).as_posix()}
    if only:
        data['only'] = only
    directory = folder / 'batches' / STEP
    store.write_atomic(directory / f'{entry["batch_id"]}.in.json', store.dump_json(data))
    entries.append(entry)
    store.write_atomic(directory / 'manifest.json', store.dump_json(entries))
    return entry


def form_batches(folder, config, entries, outcomes, now):
    import batches
    reserved = {item for entry in batches.unsettled(entries, outcomes) for item in entry['items']}
    for source, number, _url in fetch.pages(config):
        page_ref = ref(source['name'], number)
        meta = store.read_json(fetch.meta_path(folder, source['name'], number), {})
        if meta.get('status') != 'ok' or meta.get('applied') or page_ref in reserved:
            continue
        new_entry(folder, entries, page_ref, now)


def run(root, exam, now, task, config, options, get=None):
    import batches
    fetched = fetch.run(root, exam, now, get=get, config=config)
    folder = store.exam_dir(root, exam)
    entries = store.read_json(folder / 'batches' / STEP / 'manifest.json', [])
    data = store.read_json(folder / 'state.json', {})
    outcomes = data.get('dispatch', {}).get(STEP, {})
    ensure_retries(folder, entries, outcomes, now)
    form_batches(folder, config, entries, outcomes, now)
    return fetched + '\n' + batches.publish_dispatch(folder, STEP, entries, outcomes, task, options)


# Validation

def in_page(text, page, choice=False):
    key = norm(text, choice=choice)
    return bool(key) and key in page


def check_question(result, page):
    """Return the rejection reason, or '' when the question is acceptable."""
    if not isinstance(result.get('question'), str) or not isinstance(result.get('choices'), list):
        return 'Question and choices are required.'
    choices = result['choices']
    if not 2 <= len(choices) <= 6 or any(not isinstance(c, str) for c in choices):
        return 'A question needs 2 to 6 choices.'
    texts = [result['question'], *choices]
    explanations = result.get('explanations', {})
    if not isinstance(explanations, dict):
        return 'Invalid explanations.'
    texts += [v for v in explanations.values() if isinstance(v, str)]
    if any(not isinstance(v, str) for v in explanations.values()):
        return 'Invalid explanations.'
    if not all(validate.cell_text(t) for t in texts):
        return 'Text breaks the cell text rule.'
    if not in_page(result['question'], page):
        return 'Stem not found in the page text.'
    for choice in choices:
        if not in_page(choice, page, choice=True):
            return 'Choice not found in the page text.'
    letters = LETTERS[:len(choices)]
    if 'block' in explanations and len(explanations) > 1:
        return 'Explanations are either per choice or one block.'
    for key, value in explanations.items():
        if key != 'block' and key not in letters:
            return 'Explanation letter is not a choice.'
        if not in_page(value, page):
            return 'Explanation not found in the page text.'
    answer = result.get('answer', [])
    if (not isinstance(answer, list) or any(not isinstance(a, str) or a not in letters for a in answer)
            or len(set(answer)) != len(answer)):
        return 'Invalid answer letters.'
    if not isinstance(result.get('subdomain_label', ''), str):
        return 'Invalid subdomain label.'
    return ''


def source_row(exam, source, url, scraped_at, result):
    letters = LETTERS[:len(result['choices'])]
    explanations = result.get('explanations', {})
    choices = []
    for letter, text in zip(letters, result['choices']):
        choice = {'letter': letter, 'text': text}
        if explanations.get(letter):
            choice['explanation'] = explanations[letter]
        choices.append(choice)
    answer = sorted(result.get('answer', []))
    return {'exam': exam, 'lineage': 'scraped', 'question': result['question'], 'choices': choices,
            'answer': answer,
            'sources': [{'name': source, 'url': url, 'source_question_no': str(result['n']),
                         'site_answer': answer, 'community_answer': [], 'scraped_at': scraped_at,
                         'subdomain_label': result.get('subdomain_label', ''),
                         'explanation_block': explanations.get('block', '')}]}


# Apply

def key_of(result, index):
    n = result.get('n')
    return str(n) if isinstance(n, (int, str)) and not isinstance(n, bool) and str(n) else f'#{index}'


def evaluate(entry, parsed, result, error, folder, exam, now):
    """One entry's outcome: records accepted, rejected {n: reason}, skipped [(n, reason)]."""
    page_ref = entry['items'][0]
    meta = store.read_json(page_meta(folder, page_ref), {})
    source, _ = split_ref(page_ref)
    outcome = {'accepted': [], 'rejected': {}, 'parsed': parsed, 'records': [], 'skipped': []}
    if error:
        outcome['rejected'] = {'*': error}
        return outcome
    page_path = page_files(folder, page_ref)
    page = norm(page_path.read_text(encoding='utf-8')) if page_path.is_file() else ''
    seen = {}
    for index, item in enumerate(result['results']):
        if isinstance(item, dict):
            seen.setdefault(key_of(item, index), []).append((index, item))
    ok_count = 0
    for key, items in seen.items():
        index, item = items[0]
        if item.get('status') == 'skipped':
            reason = item.get('reason')
            if isinstance(reason, str) and reason.strip():
                outcome['skipped'].append((key, reason))
            else:
                outcome['rejected'][key] = 'skipped needs a reason.'
            continue
        if item.get('status') != 'ok':
            outcome['rejected'][key] = 'Unknown question status.'
            continue
        ok_count += 1
        reason = 'Duplicate question number.' if len(items) > 1 else check_question(item, page)
        if reason:
            outcome['rejected'][key] = reason
            continue
        outcome['accepted'].append(key)
        outcome['records'].append(source_row(exam, source, meta.get('url', ''), meta.get('fetched_at', now),
                                             item | {'n': item.get('n', key)}))
    outcome['ok_count'] = ok_count
    return outcome


def chain(entries, outcomes, entry):
    """The entry and its earlier attempts, newest first."""
    by_id = {e['batch_id']: e for e in entries}
    result = []
    while entry is not None:
        result.append(entry)
        entry = by_id.get(entry.get('retry_of'))
    return result


def settle(root, exam, folder, entries, outcomes, entry, now, events):
    """Close a page: write its records, its meta, and the dropped list."""
    page_ref = entry['items'][0]
    source, _ = split_ref(page_ref)
    meta_file = page_meta(folder, page_ref)
    meta = store.read_json(meta_file, {})
    steps = chain(entries, outcomes, entry)
    records, accepted = [], set()
    for step in steps:
        for record in outcomes.get(step['batch_id'], {}).get('records', []):
            number = record['sources'][0]['source_question_no']
            if number not in accepted:
                accepted.add(number)
                records.append(record)
    final = outcomes[entry['batch_id']]
    dropped = final['rejected']
    if not records:
        meta['status'] = 'failed: no questions'
        meta.pop('applied', None)
        events.append({'at': now, 'step': STEP, 'kind': 'failed_page', 'source': source,
                       'ref': meta.get('url', ''), 'reason': 'no questions'})
    else:
        path = folder / 'sources' / f'{source}.jsonl'
        url = meta.get('url', '')
        kept = [row for row in store.read_jsonl(path) if row['sources'][0]['url'] != url]
        store.write_atomic(path, store.dump_jsonl(kept + records))
        meta['applied'] = entry['batch_id']
        meta['status'] = 'done-partial' if dropped else 'ok'
        for key, reason in dropped.items():
            events.append({'at': now, 'step': STEP, 'kind': 'dropped', 'source': source,
                           'ref': key, 'reason': reason})
    final['dropped'] = dict(dropped)
    final['rejected'] = {}
    for step in steps:
        for number, reason in outcomes.get(step['batch_id'], {}).get('skipped', []):
            events.append({'at': now, 'step': STEP, 'kind': 'skipped', 'source': source,
                           'ref': f'{meta.get("url", "")}#{number}', 'reason': reason})
    store.write_atomic(meta_file, store.dump_json(meta))


def ensure_retries(folder, entries, outcomes, now):
    """Requeue entries that carry rejections, once. Safe to run again after a crash."""
    superseded = {e.get('retry_of') for e in entries}
    for entry in list(entries):
        outcome = outcomes.get(entry['batch_id'])
        if (not outcome or not outcome['rejected'] or entry['batch_id'] in superseded
                or entry['attempt'] >= 3):
            continue
        only = [int(k) for k in outcome['rejected'] if k.isdigit()]
        meta = store.read_json(page_meta(folder, entry['items'][0]), {})
        if meta.get('applied') or meta.get('status') != 'ok':
            continue
        new_entry(folder, entries, entry['items'][0], now, entry['attempt'] + 1, entry['batch_id'],
                  only if outcome['parsed'] and only and len(only) == len(outcome['rejected']) else None)


def apply(root, exam, now, step, task, config, options):
    import batches
    folder = store.exam_dir(root, exam)
    directory = folder / 'batches' / STEP
    entries = store.read_json(directory / 'manifest.json', [])
    data = store.read_json(folder / 'state.json', {})
    outcomes = data.setdefault('dispatch', {}).setdefault(STEP, {})
    ensure_retries(folder, entries, outcomes, now)
    pending = batches.unsettled(entries, outcomes)
    wave = set(data.get('dispatch_waves', {}).get(
        STEP, [entry['batch_id'] for entry in pending[:options['max_parallel']]]))
    events = []
    for entry in pending:
        path = directory / f'{entry["batch_id"]}.json'
        if entry['batch_id'] not in wave and not path.exists():
            continue
        parsed, result, error = validate.result_file(path, entry, STEP)
        outcome = evaluate(entry, parsed, result, error, folder, exam, now)
        outcomes[entry['batch_id']] = outcome
        if parsed and entry['attempt'] == 1 and not outcome['ok_count']:
            outcome['rejected'] = {}
            meta_file = page_meta(folder, entry['items'][0])
            meta = store.read_json(meta_file, {})
            meta.update(status='failed: no questions')
            meta.pop('applied', None)
            store.write_atomic(meta_file, store.dump_json(meta))
            events.append({'at': now, 'step': STEP, 'kind': 'failed_page',
                           'source': split_ref(entry['items'][0])[0], 'ref': meta.get('url', ''),
                           'reason': 'no questions'})
        elif not outcome['rejected'] or (entry['attempt'] >= 3 and parsed):
            settle(root, exam, folder, entries, outcomes, entry, now, events)
    recorded = {(e['step'], e['kind'], e['ref'], e['reason']) for e in store.read_jsonl(folder / 'log.jsonl')}
    store.append_log(root, exam, [e for e in events
                                  if (e['step'], e['kind'], e['ref'], e['reason']) not in recorded])
    store.write_atomic(folder / 'state.json', store.dump_json(data))
    ensure_retries(folder, entries, outcomes, now)
    total, done, pending_count, failed = batches.counts(folder, STEP)
    return (batches.publish_dispatch(folder, STEP, entries, outcomes, task, options)
            + f'\nBatches: total {total}, done {done}, pending {pending_count}, failed {len(failed)}'
            + (f' ({", ".join(failed)})' if failed else ''))
