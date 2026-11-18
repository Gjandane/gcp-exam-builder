import json
import shutil

import yaml
import pytest

import store
from conftest import FIXTURES, SKILL
from test_eb_cli import run_eb


def prepare(root, count=3, **options):
    path = root / 'exam-bank/config/models.yaml'
    shutil.copy(SKILL / 'templates/models.example.yaml', path)
    models = yaml.safe_load(path.read_text(encoding='utf-8'))
    models['tasks']['subdomain_tagging'].update({'batch_size': 2} | options)
    path.write_text(yaml.safe_dump(models), encoding='utf-8')
    folder = root / 'exam-bank/pmle'
    template = store.read_jsonl(FIXTURES / 'export/bank.jsonl')[0]
    rows = []
    for i in range(count):
        row = json.loads(json.dumps(template))
        row.update(id=f'q_{i:012x}', subdomain='', subdomain_by='')
        rows.append(row)
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    return folder


def command(root, name):
    result = run_eb(name, 'pmle', 'tag', cwd=root)
    assert result.returncode == 0, result.stderr
    return result.stdout


def manifest(folder):
    return store.read_json(folder / 'batches/tag/manifest.json', [])


def result_file(folder, entry, results):
    path = folder / 'batches/tag' / f'{entry["batch_id"]}.json'
    store.write_atomic(path, store.dump_json(
        {'batch_id': entry['batch_id'], 'step': 'tag', 'results': results}))
    return path


def ok(question_id, **changes):
    return {'id': question_id, 'status': 'ok', 'subdomain': '5.1',
            'confidence': 'medium', 'alt': '5.2'} | changes


def test_tag_apply_by_id_preserves_content_and_is_byte_identical_on_repeat(root):
    folder = prepare(root, count=2)
    before = store.read_jsonl(folder / 'bank.jsonl')
    command(root, 'batches')
    entry = manifest(folder)[0]
    result_file(folder, entry, [ok(before[1]['id']), ok(before[0]['id'])])
    output = command(root, 'apply')
    after = store.read_jsonl(folder / 'bank.jsonl')
    for previous, row in zip(before, after):
        assert row == previous | {'subdomain': '5.1', 'subdomain_by': 'llm',
                                  'subdomain_confidence': 'medium'}
    assert 'dispatch:\n[]' in output
    bank_bytes = (folder / 'bank.jsonl').read_bytes()
    command(root, 'apply')
    assert (folder / 'bank.jsonl').read_bytes() == bank_bytes
    assert manifest(folder) == [entry]


def test_batches_select_pending_in_bank_order_and_keep_manifest_entries(root):
    folder = prepare(root, max_parallel=99)
    rows = store.read_jsonl(folder / 'bank.jsonl')
    rows[1]['subdomain'] = '2.1'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    output = command(root, 'batches')
    entries = manifest(folder)
    assert entries[0]['items'] == ['q_000000000000', 'q_000000000002']
    assert entries[0]['attempt'] == 1 and entries[0]['retry_of'] is None
    assert set(entries[0]) == {'batch_id', 'kind', 'items', 'attempt', 'retry_of', 'created_at'}
    assert 'max_parallel: 20' in output
    assert 'exam-bank-reader' in output and 'sonnet' in output and 'low' in output
    assert 'workers/tag.md' in output and 'tag-0001.in.json' in output
    command(root, 'batches')
    assert manifest(folder) == entries


@pytest.mark.parametrize('bad', [
    {'subdomain': '99.9'}, {'subdomain': ['5.1']}, {'confidence': 'certain'},
    {'alt': '5.1'}, {'alt': '99.9'}, {'alt': None},
    {'status': 'unusable', 'reason': ''}, {'status': 'other'},
])
def test_partial_result_applies_valid_question_and_retries_only_rejected(root, bad):
    folder = prepare(root, count=2)
    command(root, 'batches')
    first = manifest(folder)[0]
    good_id, bad_id = first['items']
    result_file(folder, first, [ok(good_id), ok(bad_id, **bad), ok('outside-batch')])
    command(root, 'apply')
    rows = store.read_jsonl(folder / 'bank.jsonl')
    assert rows[0]['subdomain'] == '5.1'
    assert rows[1]['subdomain'] == ''
    entries = manifest(folder)
    assert entries[0] == first
    assert entries[1]['items'] == [bad_id]
    assert entries[1]['attempt'] == 2
    assert entries[1]['retry_of'] == first['batch_id']


def test_tag_unusable_retires_once_without_changing_updated_at(root):
    folder = prepare(root, count=1)
    before = store.read_jsonl(folder / 'bank.jsonl')[0]
    command(root, 'batches')
    entry = manifest(folder)[0]
    result_file(folder, entry, [{'id': before['id'], 'status': 'unusable',
                               'reason': 'Stem cut off.'}])
    command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl')[0] == before | {'status': 'retired'}
    event = store.read_jsonl(folder / 'log.jsonl')[0]
    assert event['kind'] == 'retired' and event['reason'] == 'Stem cut off.'
    command(root, 'apply')
    assert store.read_jsonl(folder / 'log.jsonl') == [event]


@pytest.mark.parametrize('file_kind', ['missing', 'invalid_json', 'wrong_batch', 'wrong_step', 'not_object', 'not_list'])
def test_invalid_result_exhausts_at_three_and_next_invocation_restarts(root, file_kind):
    folder = prepare(root, count=1)
    command(root, 'batches')
    for attempt in range(1, 4):
        entry = manifest(folder)[-1]
        assert entry['attempt'] == attempt
        if file_kind != 'missing':
            path = result_file(folder, entry, [ok(entry['items'][0])])
            data = json.loads(path.read_text(encoding='utf-8'))
            if file_kind == 'wrong_batch':
                data['batch_id'] = 'tag-9999'
            elif file_kind == 'wrong_step':
                data['step'] = 'answers'
            elif file_kind == 'not_object':
                data = []
            elif file_kind == 'not_list':
                data['results'] = None
            path.write_text('{bad' if file_kind == 'invalid_json' else json.dumps(data), encoding='utf-8')
        output = command(root, 'apply')
    assert len(manifest(folder)) == 3
    assert 'dispatch:\n[]' in output and 'failed 1' in output
    command(root, 'apply')
    assert len(manifest(folder)) == 3
    row = store.read_jsonl(folder / 'bank.jsonl')[0]
    assert row['status'] == 'active' and row['subdomain'] == ''
    report = run_eb('state', 'pmle', cwd=root)
    assert report.returncode == 0, report.stderr
    assert '- tag: total 3, done 2, pending 0, failed 1 (tag-0003)' in report.stdout
    command(root, 'batches')
    assert manifest(folder)[-1]['attempt'] == 1
    assert manifest(folder)[-1]['retry_of'] is None


def test_apply_does_not_retry_batches_outside_the_dispatched_wave(root):
    folder = prepare(root, count=5, max_parallel=1)
    command(root, 'batches')
    original = manifest(folder)
    result_file(folder, original[0], [ok(item) for item in original[0]['items']])
    command(root, 'apply')
    assert manifest(folder) == original
    command(root, 'apply')
    entries = manifest(folder)
    assert entries[:3] == original
    assert len(entries) == 4
    assert entries[-1]['retry_of'] == 'tag-0002'


@pytest.mark.parametrize('first_failure', ['rejected', 'missing', 'invalid_json'])
def test_auto_retire_requires_two_failed_entries_with_parsed_rejections(root, first_failure):
    folder = prepare(root, count=1)
    original = store.read_jsonl(folder / 'bank.jsonl')[0]
    needed_runs = 2 if first_failure == 'rejected' else 3
    for invocation in range(needed_runs):
        command(root, 'batches')
        for _ in range(3):
            entry = manifest(folder)[-1]
            if invocation or first_failure == 'rejected':
                result_file(folder, entry, [ok(original['id'], subdomain='99.9')])
            elif first_failure == 'invalid_json':
                (folder / 'batches/tag' / f'{entry["batch_id"]}.json').write_text('{bad', encoding='utf-8')
            output = command(root, 'apply')
        row = store.read_jsonl(folder / 'bank.jsonl')[0]
        assert row['status'] == ('retired' if invocation == needed_runs - 1 else 'active')
        assert row['updated_at'] == original['updated_at']
        assert 'dispatch:\n[]' in output
    events = store.read_jsonl(folder / 'log.jsonl')
    assert len(events) == 1
    assert events[0]['ref'] == original['id']
    assert 'two failed Batches' in events[0]['reason']
    report = run_eb('state', 'pmle', cwd=root)
    assert 'retired:' in report.stdout and 'tag-0006' in report.stdout
    command(root, 'batches')
    assert len(manifest(folder)) == needed_runs * 3


def test_completed_result_does_not_overwrite_a_new_tagging_invocation(root):
    folder = prepare(root, count=1)
    command(root, 'batches')
    entry = manifest(folder)[0]
    result_file(folder, entry, [ok(entry['items'][0])])
    command(root, 'apply')
    rows = store.read_jsonl(folder / 'bank.jsonl')
    # Merge clears a non-user tag when the guide changes.
    rows[0]['subdomain'] = ''
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    assert len(manifest(folder)) == 2
    new_entry = manifest(folder)[-1]
    result_file(folder, new_entry, [ok(new_entry['items'][0], subdomain='2.1', alt='2.2')])
    command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['subdomain'] == '2.1'


def test_tag_input_contains_titles_hints_and_source_labels_without_answers(root):
    folder = prepare(root, count=1)
    path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(path.read_text(encoding='utf-8'))
    config['sections'][0]['subdomains'][0]['hint'] = 'BigQuery ML'
    path.write_text(yaml.safe_dump(config), encoding='utf-8')
    rows = store.read_jsonl(folder / 'bank.jsonl')
    rows[0]['sources'][0]['subdomain_label'] = 'Old guide label'
    rows[0]['answer_note'] = 'SECRET'
    rows[0]['choices'][0]['explanation'] = 'SECRET'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    data = store.read_json(folder / 'batches/tag/tag-0001.in.json')
    assert len(data['sections']) == 6
    assert sum(len(s['subdomains']) for s in data['sections']) == 14
    assert data['sections'][0]['subdomains'][0]['hint'] == 'BigQuery ML'
    question = data['questions'][0]
    assert question['source_labels'] == ['Old guide label']
    assert set(question) == {'id', 'question', 'choices', 'source_labels'}
    assert all(set(c) == {'letter', 'text'} for c in question['choices'])
    assert 'SECRET' not in json.dumps(data)
    assert 'answer' not in json.dumps(data)


def test_batch_options_fall_back_to_defaults_with_task_model_settings(root):
    folder = prepare(root, count=7)
    path = root / 'exam-bank/config/models.yaml'
    models = yaml.safe_load(path.read_text(encoding='utf-8'))
    models['defaults'].update(batch_size=3, max_parallel=2)
    models['tasks']['subdomain_tagging'] = {'alias': 'haiku', 'effort': 'high'}
    path.write_text(yaml.safe_dump(models), encoding='utf-8')
    output = command(root, 'batches')
    assert [len(e['items']) for e in manifest(folder)] == [3, 3, 1]
    assert 'max_parallel: 2' in output
    assert '"alias": "haiku"' in output and '"effort": "high"' in output


def test_duplicate_and_omitted_question_results_requeue_without_touching_valid_rows(root):
    folder = prepare(root, count=3, batch_size=3)
    command(root, 'batches')
    entry = manifest(folder)[0]
    first, second, third = entry['items']
    result_file(folder, entry, [ok(first), ok(second), ok(second)])
    command(root, 'apply')
    assert manifest(folder)[-1]['items'] == [second, third]
    rows = store.read_jsonl(folder / 'bank.jsonl')
    assert [row['subdomain'] for row in rows] == ['5.1', '', '']


def test_resume_preserves_completed_worker_files_until_apply(root):
    folder = prepare(root, count=3, max_parallel=1)
    command(root, 'batches')
    first, second = manifest(folder)
    path = result_file(folder, first, [ok(item) for item in first['items']])
    before = path.read_bytes()
    output = command(root, 'batches')
    assert first['batch_id'] not in output
    assert second['batch_id'] in output
    assert path.read_bytes() == before
    assert len(manifest(folder)) == 2
    result_file(folder, second, [ok(item) for item in second['items']])
    assert 'dispatch:\n[]' in command(root, 'batches')
    assert 'dispatch:\n[]' in command(root, 'apply')
    assert all(row['subdomain'] for row in store.read_jsonl(folder / 'bank.jsonl'))


def test_resumed_wave_retries_its_missing_worker_while_applying_prior_results(root):
    folder = prepare(root, count=3, max_parallel=1)
    command(root, 'batches')
    first, second = manifest(folder)
    result_file(folder, first, [ok(item) for item in first['items']])
    command(root, 'batches')
    # The resumed session dispatched the second Batch, whose worker failed to write.
    command(root, 'apply')
    entries = manifest(folder)
    assert entries[-1]['retry_of'] == second['batch_id']
    assert entries[-1]['attempt'] == 2
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['subdomain'] == '5.1'


@pytest.mark.parametrize('envelope', [[], {'batch_id': 'wrong', 'step': 'tag', 'results': []}])
def test_invalid_envelopes_never_count_as_question_retirement_evidence(root, envelope):
    folder = prepare(root, count=1)
    for _ in range(2):
        command(root, 'batches')
        for _ in range(3):
            entry = manifest(folder)[-1]
            path = folder / 'batches/tag' / f'{entry["batch_id"]}.json'
            path.write_text(json.dumps(envelope), encoding='utf-8')
            command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['status'] == 'active'


@pytest.mark.parametrize('failure_location', ['log', 'bank'])
def test_retirement_recovers_after_write_failure(root, failure_location):
    folder = prepare(root, count=1)
    command(root, 'batches')
    entry = manifest(folder)[0]
    result_file(folder, entry, [{'id': entry['items'][0], 'status': 'unusable',
                               'reason': 'Stem cut off.'}])
    # A directory at a write path forces a real filesystem write failure.
    log_path = folder / 'log.jsonl'
    obstruction = log_path if failure_location == 'log' else folder / 'bank.jsonl.tmp'
    obstruction.mkdir()
    failure = run_eb('apply', 'pmle', 'tag', cwd=root)
    assert failure.returncode == 1
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['status'] == 'active'
    obstruction.rmdir()
    command(root, 'apply')
    command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['status'] == 'retired'
    assert len(store.read_jsonl(log_path)) == 1
    assert store.read_jsonl(log_path)[0]['reason'] == 'Stem cut off.'
