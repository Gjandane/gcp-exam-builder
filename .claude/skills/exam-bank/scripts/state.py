"""Rebuild the human-readable state from the files on disk."""
import csv
import io

import batches
import export
import setup
import store

STEPS = ('setup', 'scrape', 'llm-scrape', 'intake', 'merge', 'tag', 'answers',
         'explanations', 'augment', 'export')
ROUTES = STEPS + ('study-guide', 'recheck')


def available_exam_config(root, exam):
    """Keep usable exam data visible when another setup check fails."""
    try:
        import yaml
    except ImportError:
        return {}
    try:
        config = store.load_exam_config(root, exam)
        store.subdomain_titles(config)
        export.render_meta(config, str(config['guide_version']), '')
        for key in ('curated_sites', 'llm_sources'):
            sources = config.get(key, [])
            if not isinstance(sources, list):
                return {}
            for source in sources:
                if not isinstance(source, dict) or not isinstance(source.get('name'), str):
                    return {}
                if key == 'llm_sources' and not isinstance(source.get('urls', []), list):
                    return {}
        return config
    except (store.Stop, ValueError, TypeError, KeyError, AttributeError, OSError, yaml.YAMLError):
        return {}


def export_difference(folder, exam, rows, config):
    path = folder / 'export' / f'{exam}-questions.csv'
    meta_path = folder / 'bank_meta.json'
    rendered = export.render_csv(rows, config)
    previous = path.read_bytes() if path.is_file() else b''
    try:
        old_rows = {row['id']: row for row in csv.DictReader(io.StringIO(previous.decode('utf-8'), newline=''))}
        new_rows = {row['id']: row for row in csv.DictReader(io.StringIO(rendered.decode('utf-8'), newline=''))}
        differing = sum(old_rows.get(key) != new_rows.get(key) for key in old_rows.keys() | new_rows.keys())
        meta = store.read_json(meta_path, {})
        # Retain the recorded timestamp but compare every other byte, including
        # whitespace and key order, with the actual export renderer.
        expected = export.render_meta(config, str(config['guide_version']), meta.get('exported_at', ''))
        meta_matches = meta_path.is_file() and meta_path.read_bytes() == expected
    except (ValueError, KeyError, UnicodeError, TypeError):
        differing, meta_matches = len(rows), False
    return previous != rendered or not meta_matches or not meta_path.is_file(), differing


def run(root, exam, now, forced=None):
    if forced and forced not in ROUTES:
        raise store.Stop('Unknown step. Valid names: ' + ', '.join(ROUTES))
    folder = store.exam_dir(root, exam)
    data = store.read_json(folder / 'state.json', {})
    try:
        config = setup.check_config(root, exam)
        setup_ok = bool(data.get('setup', {}).get('passed_at'))
        setup_error = ''
    except store.Stop as error:
        config = available_exam_config(root, exam)
        setup_ok = False
        setup_error = str(error)
    rows = store.read_jsonl(folder / 'bank.jsonl')
    active = [r for r in rows if r.get('status') == 'active']
    statuses = {'setup': 'done' if setup_ok else 'pending'}
    source_lines = []
    for kind, key in (('curated', 'curated_sites'), ('llm-scrape', 'llm_sources')):
        sources = config.get(key, [])
        enabled = [s for s in sources if s.get('enabled')]
        open_sources = []
        for source in sources:
            name = source['name']
            progress = store.read_json(folder / 'sources' / f'{name}.progress.json', {})
            total, done = progress.get('pages_total', 0), progress.get('pages_done', 0)
            gate = data.get('gates', {}).get(name)
            paywall_page = progress.get('paywall_page') if done == progress.get('paywall_page', 0) - 1 else None
            pending = source.get('enabled') and not paywall_page and (not total or done < total)
            if kind == 'llm-scrape':
                total = len(source.get('urls', []))
                done = 0
                for i, url in enumerate(source.get('urls', []), 1):
                    page = store.read_json(folder / 'raw' / name / f'{i:02d}.meta.json', {})
                    page_status = page.get('status', '')
                    if page_status.startswith('failed:'):
                        done += 1
                        source_lines.append(f'| {name} {i:02d} | {kind} | {page_status} | 1/1 | | {page.get("fetched_at", "")} |')
                        continue
                    if page_status == 'done-partial' or page.get('applied'):
                        done += 1
                pending = source.get('enabled') and done < total
            if source.get('enabled') and (pending or gate):
                open_sources.append(gate or True)
            status = 'skipped' if not source.get('enabled') else ('waiting on user: ' + gate if gate else 'pending' if pending else f'done: paywall at page {paywall_page}' if paywall_page and kind == 'curated' else 'done')
            count = len(store.read_jsonl(folder / 'sources' / f'{name}.jsonl'))
            source_lines.append(f'| {name} | {kind} | {status} | {done}/{total} | {count} | {progress.get("last_run", "")} |')
        step = 'scrape' if kind == 'curated' else 'llm-scrape'
        statuses[step] = 'skipped' if not enabled else ('waiting on user' if any(isinstance(x, str) for x in open_sources) else 'pending' if open_sources else 'done')
    given = list((folder / 'given').glob('*.md'))
    statuses['intake'] = 'skipped' if not given else 'done' if (folder / 'sources/given.jsonl').exists() else 'pending'
    for name in ('given', 'created'):
        source_path = folder / 'sources' / f'{name}.jsonl'
        if source_path.exists() or (name == 'given' and given):
            records = store.read_jsonl(source_path)
            times = [source.get('scraped_at', '') for record in records
                     for source in record.get('sources', [])]
            status = statuses['intake'] if name == 'given' else 'done'
            source_lines.append(f'| {name} | {name} | {status} | - | {len(records)} | {max(times, default="")} |')
    hashes = {f'sources/{p.name}': store.sha256_file(p) for p in (folder / 'sources').glob('*.jsonl')}
    meta = store.read_json(folder / 'bank_meta.json', {})
    statuses['merge'] = 'done' if hashes == data.get('merged', {}) and meta.get('guide_version') == config.get('guide_version') and (folder / 'bank.jsonl').exists() else 'pending'
    statuses['tag'] = 'pending' if any(not r.get('subdomain') for r in active) else 'done'
    answer_pending = lambda r: (not r.get('answer') or r.get('uncertain')) and not r.get('answer_checked_at')
    statuses['answers'] = 'pending' if any(answer_pending(r) for r in active) else 'done'
    statuses['explanations'] = 'pending' if any(not answer_pending(r) and any(not c.get('explanation') for c in r.get('choices', [])) for r in active) else 'done'
    counts = {step: batches.counts(folder, step) for step in (*STEPS, 'recheck')}
    opt = data.get('augment', {}).get('opt_in')
    statuses['augment'] = 'pending' if opt is None or (opt and (counts['augment'][2] or counts['augment'][3])) else 'done' if opt else 'skipped'
    for step in STEPS:
        _, done, pending, failed = counts[step]
        if statuses.get(step) == 'pending' and done and (pending or failed):
            statuses[step] = 'in progress'
    stale, differing = export_difference(folder, exam, rows, config) if config else (True, 0)
    statuses['export'] = 'pending' if stale else 'done'
    current = next((s for s in STEPS if statuses[s] not in ('done', 'skipped')), 'export')
    selected = forced or current
    path = f'.claude/skills/exam-bank/steps/{STEPS.index(selected)+1:02d}-{selected}.md' if selected in STEPS else f'.claude/skills/exam-bank/steps/{selected}.md'
    lines = [f'# {exam}: {config.get("name", exam)}', f'Current step: {current}', f'Next command: /exam-bank {exam}' if current != 'export' or stale else 'Next command: none', '', '## Steps']
    lines += [f'- {step}: {statuses[step]}' for step in STEPS]
    lines += ['', '## Sources', '| Name | Kind | Status | Pages | Questions | Last run |', '| --- | --- | --- | --- | --- | --- |', *source_lines, '', '## Batches']
    lines += [f'- {step}: total {total}, done {done}, pending {pending}, failed {len(failed)}' + (f' ({", ".join(failed)})' if failed else '') for step, (total, done, pending, failed) in counts.items()]
    lines += ['', '## Notes']
    if setup_error:
        lines.append(f'- setup: {setup_error}')
    log = store.read_jsonl(folder / 'log.jsonl')
    for event in log:
        if event.get('step') == 'augment' and event.get('kind') == 'dropped':
            continue
        lines.append(f'- {event.get("kind", "")}: {event.get("source", "")} {event.get("ref", "")} {event.get("reason", "")}')
    lines.append(f'- augment drops: {sum(e.get("step") == "augment" and e.get("kind") == "dropped" for e in log)}')
    recheck_entries = {e['batch_id']: e for e in store.read_json(folder / 'batches/recheck/manifest.json', [])}
    for batch_id in counts['recheck'][3]:
        lines.append(f'- recheck failed: {batch_id} stays active, Report open: '
                     + ', '.join(recheck_entries[batch_id]['items']))
    low = sum(r.get('subdomain_confidence') == 'low' for r in active)
    lines.append(f'- low subdomain tags: {low}')
    lines += ['', '## Export', 'done' if not stale else f'pending: bank changed since last export ({differing} rows differ)']
    report = '\n'.join(lines) + '\n'
    store.write_atomic(folder / 'state.md', report.encode('utf-8'))
    return report + f'\nRun step: {selected}\nStep file: {path}'
