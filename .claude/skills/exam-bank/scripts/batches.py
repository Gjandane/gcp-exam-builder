"""Append-only Batch dispatch. Task adapters own pending work and row changes."""
import json
import pathlib

import recheck
import setup
import store
import validate


class TagTask:
    task = 'subdomain_tagging'
    agent = 'exam-bank-reader'
    worker = 'tag'
    auto_retire = True
    validate = staticmethod(validate.tag)

    def pending(self, row):
        return row.get('status') == 'active' and not row.get('subdomain')

    def input(self, entry, rows, config):
        return {
            'batch_id': entry['batch_id'], 'step': entry['kind'],
            'sections': [
                {'number': section['number'], 'title': section['title'],
                 'subdomains': section['subdomains']}
                for section in config['sections']
            ],
            'questions': [
                {'id': row['id'], 'question': row['question'],
                 'choices': [{'letter': c['letter'], 'text': c['text']} for c in row['choices']],
                 'source_labels': [s['subdomain_label'] for s in row.get('sources', [])
                                   if s.get('subdomain_label')]}
                for row in rows
            ],
        }

    def apply(self, row, result, now):
        if result['status'] == 'unusable':
            row['status'] = 'retired'
            return result['reason']
        row.update(subdomain=result['subdomain'], subdomain_by='llm',
                   subdomain_confidence=result['confidence'])
        return None


def explanation_by(row):
    written = [c['explanation_by'] for c in row['choices'] if c.get('explanation')]
    return ('llm' if 'llm' in written else 'user' if written and all(x == 'user' for x in written)
            else 'source' if written else '')


def answers_pending(row):
    return (not row.get('answer') or row.get('uncertain')) and not row.get('answer_checked_at')


class AnswersTask:
    task = 'answer_filling'
    agent = 'exam-bank-researcher'
    worker = 'answers'
    auto_retire = True

    def pending(self, row):
        return row.get('status') == 'active' and answers_pending(row)

    def input(self, entry, rows, config):
        sources = {}
        for row in rows:
            answers = []
            for source in row.get('sources', []):
                for field, suffix in [('site_answer', ''), ('community_answer', '-community')]:
                    if source.get(field):
                        answers.append({'name': source['name'] + suffix, 'answer': source[field]})
            sources[row['id']] = {
                'stored': row.get('answer', []), 'sources': answers,
                'explanations': {c['letter']: {'text': c['explanation'], 'by': c['explanation_by']}
                                 for c in row['choices'] if c.get('explanation')},
                'explanation_blocks': [s['explanation_block'] for s in row.get('sources', [])
                                       if s.get('explanation_block')]}
        return {'batch_id': entry['batch_id'], 'step': entry['kind'],
                'questions': [{'id': row['id'], 'question': row['question'],
                               'choices': [{'letter': c['letter'], 'text': c['text']}
                                           for c in row['choices']]} for row in rows],
                'source_answers': sources}

    def validate(self, result, config, row):
        return validate.answers(result, row)

    def apply(self, row, result, now):
        if result['status'] == 'unusable':
            row['status'] = 'retired'
            return result['reason']
        previous = row.get('answer', [])
        answer = sorted(result['answer'])
        preserve = validate.preserves_user_ticks(row)
        disputed = preserve and answer != sorted(previous)
        note = result['note']
        if disputed:
            row['uncertain'] = True
            note = (note + ' ' if note else '') + 'LLM answer: ' + ','.join(answer) + '.'
        if not preserve:
            row['answer'] = answer
            row['answer_by'] = 'llm'
        if not previous and result['confidence'] == 'low':
            row['uncertain'] = True
        if not disputed:
            for choice in row['choices']:
                if choice.get('explanation_by') != 'user' and choice['letter'] in result['explanations']:
                    choice.update(explanation=result['explanations'][choice['letter']], explanation_by='llm')
        conflicts = result['why_conflicts']
        if conflicts:
            row['uncertain'] = True
            for letter in conflicts:
                note = (note + ' ' if note else '') + f'Your Why: on {letter} contradicts this answer.'
        row['explanation_by'] = explanation_by(row)
        row.update(answer_confidence=result['confidence'], answer_note=note,
                   answer_refs=result['refs'], answer_checked_at=now, updated_at=now)
        return None


class ExplanationsTask:
    task = 'explanation_writing'
    agent = 'exam-bank-researcher'
    worker = 'explanations'
    auto_retire = True

    def pending(self, row):
        return (row.get('status') == 'active' and not answers_pending(row) and
                any(not c.get('explanation') for c in row['choices']))

    def input(self, entry, rows, config):
        return {'batch_id': entry['batch_id'], 'step': entry['kind'],
                'questions': [{
                    'id': row['id'], 'question': row['question'],
                    'choices': [{'letter': c['letter'], 'text': c['text']} for c in row['choices']],
                    'answer': row.get('answer', []),
                    'explanations': {c['letter']: {'text': c['explanation'], 'by': c['explanation_by']}
                                     for c in row['choices'] if c.get('explanation')},
                    'explanation_blocks': [s['explanation_block'] for s in row.get('sources', [])
                                           if s.get('explanation_block')]} for row in rows]}

    def validate(self, result, config, row):
        return validate.explanations(result, row)

    def apply(self, row, result, now):
        if result['status'] == 'doubt' and not row.get('answer_checked_at'):
            # The row turns pending for answers, which sets the check mark, so this happens once.
            row['uncertain'] = True
            return None
        for choice in row['choices']:
            if not choice.get('explanation') and choice['letter'] in result['explanations']:
                choice.update(explanation=result['explanations'][choice['letter']], explanation_by='llm')
        row['explanation_by'] = explanation_by(row)
        if result['status'] == 'doubt':
            reason = ' '.join(result['reason'].split())
            note = row.get('answer_note', '')
            row['answer_note'] = (note + ' ' if note else '') + 'Explanations doubt: ' + reason
        row['updated_at'] = now
        return None


class RecheckTask(AnswersTask):
    """Report re-check: the answers worker and apply rules, driven by the newest Reports CSV."""
    task = 'report_recheck'
    auto_retire = False

    def load(self, folder):
        self.path, self.reports, self.skipped = recheck.plan(
            folder, store.read_jsonl(folder / 'bank.jsonl'))

    def open_reports(self, row):
        return [report for report in self.reports.get(row['id'], [])
                if recheck.later(report['reported_at'], row.get('rechecked_at', ''))]

    def pending(self, row):
        return row.get('status') == 'active' and bool(self.open_reports(row))

    def input(self, entry, rows, config):
        data = super().input(entry, rows, config)
        data['report_notes'] = {
            row['id']: ' | '.join(r['note'] for r in self.open_reports(row) if r['note'])
            for row in rows}
        return data

    def validate(self, result, config, row):
        error = validate.answers(result, row)
        if error:
            return error
        text = result.get('reason') if result.get('status') == 'unusable' else result.get('note')
        return '' if validate.cell_text(text) else 'Invalid note text.'

    def apply(self, row, result, now):
        updated_at = row.get('updated_at', '')
        previous = sorted(row.get('answer', []))
        content = lambda: (sorted(row.get('answer', [])), [c.get('explanation', '') for c in row['choices']])
        before = content()
        if result['status'] == 'unusable':
            detail = super().apply(row, result, now)
            prefix = 'Retired.'
        else:
            answer = sorted(result['answer'])
            detail = result['note']
            keeps_user = validate.preserves_user_ticks(row)
            if answer == previous:
                prefix = 'Confirmed.'
                if result['confidence'] == 'high':
                    row['uncertain'] = False
            elif keeps_user:
                prefix = f'Kept your answer {",".join(previous)}. The re-check suggests {",".join(answer)}.'
            else:
                prefix = f'Changed from {",".join(previous) or "none"} to {",".join(answer)}.'
            super().apply(row, result, now)
            if answer != previous and not keeps_user:
                row['uncertain'] = True
        if content() == before:
            row['updated_at'] = updated_at
        row['rechecked_at'] = now
        row['recheck_note'] = ' '.join(f'{prefix} {detail}'.split())[:300]
        return None


class LlmScrapeTask:
    """One Batch is one saved page. `llm_scrape` owns its forming and applying."""
    task = 'llm_scraping'
    agent = 'exam-bank-reader'
    worker = 'llm-scrape'


class AugmentTask:
    """Create and verify Batches. `augment` owns forming, options and applying."""
    task = 'augmentation'
    agent = 'exam-bank-researcher'
    worker = 'augment'


TASKS = {'tag': TagTask(), 'answers': AnswersTask(), 'explanations': ExplanationsTask(),
         'llm-scrape': LlmScrapeTask(), 'augment': AugmentTask(), 'recheck': RecheckTask()}


def configuration(root, exam, step):
    if step not in TASKS:
        raise store.Stop('Dispatch steps available: ' + ', '.join(TASKS))
    config = setup.check_config(root, exam)
    import yaml
    models = yaml.safe_load((root / 'exam-bank/config/models.yaml').read_text(encoding='utf-8'))
    task = TASKS[step]
    if hasattr(task, 'load'):
        task.load(store.exam_dir(root, exam))
    options = models['defaults'] | models['tasks'][task.task]
    options['max_parallel'] = min(options['max_parallel'], 20)
    return task, config, options


def unsettled(entries, outcomes):
    superseded = {entry['retry_of'] for entry in entries if entry.get('retry_of')}
    return [entry for entry in entries
            if entry['batch_id'] not in superseded and entry['batch_id'] not in outcomes]


def dispatchable(folder, step, entries, outcomes):
    """Keep finished worker files intact while they await application."""
    directory = folder / 'batches' / step
    return [entry for entry in unsettled(entries, outcomes)
            if validate.result_file(directory / f'{entry["batch_id"]}.json', entry, step)[1] is None]


def append_batch(folder, step, entries, task, rows, config, now, attempt=1, retry_of=None):
    sequence = max((int(entry['batch_id'].rsplit('-', 1)[1]) for entry in entries), default=0) + 1
    entry = {'batch_id': f'{step}-{sequence:04d}', 'kind': step,
             'items': [row['id'] for row in rows], 'attempt': attempt,
             'retry_of': retry_of, 'created_at': now}
    directory = folder / 'batches' / step
    store.write_atomic(directory / f'{entry["batch_id"]}.in.json',
                       store.dump_json(task.input(entry, rows, config)))
    entries.append(entry)
    store.write_atomic(directory / 'manifest.json', store.dump_json(entries))
    return entry


def publish_dispatch(folder, step, entries, outcomes, task, options):
    lines = [f'max_parallel: {options["max_parallel"]}', 'dispatch:']
    pending = dispatchable(folder, step, entries, outcomes)
    # Files alone cannot show which missing workers were actually launched.
    # Record the emitted wave before the caller spawns it.
    data = store.read_json(folder / 'state.json', {})
    data.setdefault('dispatch_waves', {})[step] = [
        entry['batch_id'] for entry in pending[:options['max_parallel']]]
    store.write_atomic(folder / 'state.json', store.dump_json(data))
    if not pending:
        lines.append('[]')
    for entry in pending:
        batch_id = entry['batch_id']
        directory = folder / 'batches' / step
        lines.append(json.dumps({
            'batch_id': batch_id, 'input_path': (directory / f'{batch_id}.in.json').as_posix(),
            'result_path': (directory / f'{batch_id}.json').as_posix(),
            'worker_file': (pathlib.Path(__file__).resolve().parents[1] / 'workers' / f'{task.worker}.md').as_posix(),
            'subagent_type': task.agent, 'alias': options['alias'], 'effort': options['effort'],
        }, ensure_ascii=False))
    return '\n'.join(lines)


def counts(folder, step):
    """Count superseded entries as completed dispatch work, preserving failed IDs."""
    directory = folder / 'batches' / step
    entries = store.read_json(directory / 'manifest.json', [])
    data = store.read_json(folder / 'state.json', {})
    outcomes = data.get('dispatch', {}).get(step, {})
    superseded = {entry.get('retry_of') for entry in entries}
    done = pending = 0
    failed = []
    for entry in entries:
        batch_id = entry['batch_id']
        if batch_id in superseded:
            done += 1
            continue
        outcome = outcomes.get(batch_id)
        if outcome is not None:
            rejected = bool(outcome['rejected'])
        else:
            _, result, _ = validate.result_file(directory / f'{batch_id}.json', entry, step)
            rejected = result is None
        if not rejected:
            done += 1
        elif entry.get('attempt', 1) >= 3:
            failed.append(batch_id)
        else:
            pending += 1
    return len(entries), done, pending, failed


def run(root, exam, now, step):
    if step == 'augment':
        import augment
        return augment.run(root, exam, now)
    task, config, options = configuration(root, exam, step)
    if step == 'llm-scrape':
        import llm_scrape
        return llm_scrape.run(root, exam, now, task, config, options)
    folder = store.exam_dir(root, exam)
    entries = store.read_json(folder / 'batches' / step / 'manifest.json', [])
    data = store.read_json(folder / 'state.json', {})
    outcomes = data.get('dispatch', {}).get(step, {})
    all_rows = store.read_jsonl(folder / 'bank.jsonl')
    restore_retries(folder, step, entries, outcomes, task, all_rows, config, now)
    reserved = {item for entry in unsettled(entries, outcomes) for item in entry['items']}
    rows = [row for row in all_rows
            if task.pending(row) and row['id'] not in reserved]
    size = options['batch_size']
    for start in range(0, len(rows), size):
        append_batch(folder, step, entries, task, rows[start:start + size], config, now)
    text = publish_dispatch(folder, step, entries, outcomes, task, options)
    if step == 'recheck':
        skipped = [f'skipped {reason} question: {item}' for item, reason in task.skipped]
        text = '\n'.join([f'reports: {task.path.name}', *skipped, text])
    return text


def restore_retries(folder, step, entries, outcomes, task, rows, config, now):
    """Recover even if a previous process stopped after recording an outcome."""
    superseded = {entry.get('retry_of') for entry in entries}
    by_id = {row['id']: row for row in rows}
    for entry in list(entries):
        outcome = outcomes.get(entry['batch_id'])
        if not outcome or entry['batch_id'] in superseded or entry['attempt'] >= 3:
            continue
        retry = [by_id[item] for item in entry['items']
                 if item in outcome['rejected'] and item in by_id and task.pending(by_id[item])]
        if retry:
            append_batch(folder, step, entries, task, retry, config, now,
                         entry['attempt'] + 1, entry['batch_id'])


def apply(root, exam, now, step):
    if step == 'augment':
        import augment
        return augment.apply(root, exam, now)
    task, config, options = configuration(root, exam, step)
    if step == 'llm-scrape':
        import llm_scrape
        return llm_scrape.apply(root, exam, now, step, task, config, options)
    folder = store.exam_dir(root, exam)
    directory = folder / 'batches' / step
    entries = store.read_json(directory / 'manifest.json', [])
    data = store.read_json(folder / 'state.json', {})
    # Application receipts distinguish an exhausted Batch from one not yet run.
    # They also stop historical results overwriting later edits or guide resets.
    outcomes = data.setdefault('dispatch', {}).setdefault(step, {})
    rows = store.read_jsonl(folder / 'bank.jsonl')
    before = store.dump_jsonl(rows)
    by_id = {row['id']: row for row in rows}
    restore_retries(folder, step, entries, outcomes, task, rows, config, now)
    pending = unsettled(entries, outcomes)
    wave = set(data.get('dispatch_waves', {}).get(
        step, [entry['batch_id'] for entry in pending[:options['max_parallel']]]))
    events = []
    for entry in pending:
        path = directory / f'{entry["batch_id"]}.json'
        # Unlaunched Batches beyond the current wave must not burn an attempt.
        if entry['batch_id'] not in wave and not path.exists():
            continue
        parsed, result, error = validate.result_file(path, entry, step)
        def check(value, cfg):
            if step in ('answers', 'explanations', 'recheck'):
                row = by_id.get(value['id'])
                return task.validate(value, cfg, row) if row else 'Question no longer exists.'
            return task.validate(value, cfg)
        accepted, rejected = validate.questions(entry, result, error, check, config)
        for item, value in accepted.items():
            row = by_id.get(item)
            if row is not None and task.pending(row):
                reason = task.apply(row, value, now)
                if reason:
                    events.append({'at': now, 'step': step, 'kind': 'retired',
                                   'source': '', 'ref': item, 'reason': reason})
        outcomes[entry['batch_id']] = {'accepted': list(accepted), 'rejected': rejected,
                                       'parsed': parsed}
    if task.auto_retire:
        for row in rows:
            if not task.pending(row):
                continue
            failures = [outcomes[entry['batch_id']]['rejected'][row['id']]
                        for entry in entries if entry.get('attempt') == 3
                        and entry['batch_id'] in outcomes
                        and outcomes[entry['batch_id']]['parsed']
                        and row['id'] in outcomes[entry['batch_id']]['rejected']]
            if len(failures) >= 2:
                row['status'] = 'retired'
                events.append({'at': now, 'step': step, 'kind': 'retired', 'source': '',
                               'ref': row['id'], 'reason': 'Validation rejected in two failed Batches: ' + failures[-1]})
    after = store.dump_jsonl(rows)
    if events:
        # Log first so a committed retirement always has its reason. If the
        # bank write then fails, the next apply replays safely without a duplicate.
        recorded = {(event['step'], event['kind'], event['ref'], event['reason'])
                    for event in store.read_jsonl(folder / 'log.jsonl')}
        store.append_log(root, exam, [event for event in events
                         if (event['step'], event['kind'], event['ref'], event['reason']) not in recorded])
    if after != before:
        store.write_atomic(folder / 'bank.jsonl', after)
    store.write_atomic(folder / 'state.json', store.dump_json(data))
    restore_retries(folder, step, entries, outcomes, task, rows, config, now)
    total, done, pending_count, failed = counts(folder, step)
    text = (publish_dispatch(folder, step, entries, outcomes, task, options)
            + f'\nBatches: total {total}, done {done}, pending {pending_count}, failed {len(failed)}'
            + (f' ({", ".join(failed)})' if failed else ''))
    if step == 'recheck' and not dispatchable(folder, step, entries, outcomes):
        steps = pathlib.Path(__file__).resolve().parents[1] / 'templates' / 'import-steps.txt'
        text += (f'\n\nNext: /exam-bank {exam} export\n\n'
                 + steps.read_text(encoding='utf-8').rstrip('\n'))
    return text
