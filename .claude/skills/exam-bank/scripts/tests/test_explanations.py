import json

import pytest
import store
from test_batches import prepare
from test_eb_cli import run_eb


def command(root, action, step='explanations'):
    result = run_eb(action, 'pmle', step, cwd=root)
    assert result.returncode == 0, result.stderr
    return result.stdout


def state(root):
    result = run_eb('state', 'pmle', cwd=root)
    assert result.returncode == 0, result.stderr
    return result.stdout


def setup_rows(root, count=1, checked=''):
    """Rows with an answer, optionally checked, and no explanations."""
    folder = prepare(root, count=count)
    rows = store.read_jsonl(folder / 'bank.jsonl')
    for row in rows:
        row.update(answer=['A'], answer_by='source', answer_checked_at=checked, uncertain=False,
                   answer_note='', explanation_by='', updated_at='2026-01-01T00:00:00Z')
        for choice in row['choices']:
            choice.update(explanation='', explanation_by='')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    return folder, rows


def write_result(folder, result):
    path = folder / 'batches/explanations/explanations-0001.json'
    store.write_atomic(path, store.dump_json(
        {'batch_id': 'explanations-0001', 'step': 'explanations', 'results': [result]}))


def good(row, **changes):
    return {'id': row['id'], 'status': 'ok', 'refs': ['https://cloud.google.com/dataflow/docs'],
            'explanations': {c['letter']: ('Correct. ' if c['letter'] == 'A' else 'Incorrect. ') + 'A fact.'
                             for c in row['choices'] if not c['explanation']}} | changes


def test_pending_and_input_shape(root):
    folder, rows = setup_rows(root, 3, checked='2026-01-01T00:00:00Z')
    rows[1].update(answer=[], answer_checked_at='')           # pending for answers
    rows[2]['choices'][0].update(explanation='Source text', explanation_by='source')
    rows[2]['choices'][1].update(explanation='User text', explanation_by='user')
    rows[2]['sources'][0]['explanation_block'] = 'Block'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    manifest = store.read_json(folder / 'batches/explanations/manifest.json')
    assert manifest[0]['items'][0] == rows[0]['id']
    assert rows[1]['id'] not in manifest[0]['items']
    data = store.read_json(folder / 'batches/explanations/explanations-0001.in.json')
    question = data['questions'][0]
    assert set(question) == {'id', 'question', 'choices', 'answer', 'explanations', 'explanation_blocks'}
    assert question['answer'] == ['A'] and 'source_answers' not in data
    assert all(set(c) == {'letter', 'text'} for c in question['choices'])


def test_row_with_all_explanations_is_not_pending(root):
    folder, rows = setup_rows(root)
    for choice in rows[0]['choices']:
        choice.update(explanation='Done.', explanation_by='source')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    assert command(root, 'batches').splitlines()[-1] == '[]'


def test_ok_applies_explanations_by_llm(root):
    folder, rows = setup_rows(root)
    rows[0]['choices'][1].update(explanation='User Why.', explanation_by='user')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    result = good(rows[0])
    result['explanations']['B'] = 'Incorrect. Overwrite attempt.'      # present choice: ignored
    write_result(folder, result)
    command(root, 'apply')
    row = store.read_jsonl(folder / 'bank.jsonl')[0]
    assert row['choices'][0]['explanation'].startswith('Correct.')
    assert row['choices'][0]['explanation_by'] == 'llm'
    assert row['choices'][1] == {**rows[0]['choices'][1]}
    assert row['explanation_by'] == 'llm' and row['updated_at'] != '2026-01-01T00:00:00Z'
    assert row['answer'] == ['A'] and row['answer_by'] == 'source' and not row['uncertain']
    assert all(c['explanation'] for c in row['choices'])


def test_doubt_on_unchecked_row_goes_back_to_answers_once(root):
    folder, rows = setup_rows(root)
    command(root, 'batches')
    write_result(folder, good(rows[0], status='doubt', reason='Docs say B.'))
    command(root, 'apply')
    row = store.read_jsonl(folder / 'bank.jsonl')[0]
    assert row['uncertain'] is True and row['answer'] == ['A']
    assert all(not c['explanation'] for c in row['choices'])
    assert row['updated_at'] == '2026-01-01T00:00:00Z' and row['answer_note'] == ''
    report = state(root)   # setup and merge are out of scope here, so read the step lines
    assert '- answers: pending' in report and '- explanations: done' in report
    assert command(root, 'batches').splitlines()[-1] == '[]'   # not pending for explanations
    # Once answers sets the mark, the row is pending for explanations and doubt cannot loop.
    row.update(answer_checked_at='2026-02-01T00:00:00Z')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl([row]))
    assert 'explanations-0002' in command(root, 'batches')


def test_doubt_on_checked_row_applies_and_extends_note(root):
    folder, rows = setup_rows(root, checked='2026-01-01T00:00:00Z')
    rows[0]['answer_note'] = 'Earlier note.'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    write_result(folder, good(rows[0], status='doubt', reason='Docs say\nB.'))
    command(root, 'apply')
    row = store.read_jsonl(folder / 'bank.jsonl')[0]
    assert all(c['explanation_by'] == 'llm' for c in row['choices'])
    assert row['answer_note'] == 'Earlier note. Explanations doubt: Docs say B.'
    assert row['uncertain'] is False and row['updated_at'] != '2026-01-01T00:00:00Z'
    assert '- explanations: done' in state(root)


@pytest.mark.parametrize('changes', [
    {'status': 'maybe'}, {'status': 'doubt'}, {'status': 'doubt', 'reason': '  '},
    {'status': 'doubt', 'reason': '<b>x</b>'}, {'explanations': {}},
    {'explanations': {'A': 'Correct. Fine.'}}, {'explanations': {'A': '', 'B': 'Incorrect. x'}},
    {'explanations': {'A': '<b>Bad</b>', 'B': 'Incorrect. x'}},
    {'explanations': {'A': 'Correct. x', 'B': 'Incorrect. x', 'Z': 'Incorrect. x'}},
    {'refs': ['https://example.com/docs']},
    {'explanations': {'A': 'Correct. See https://example.com/a', 'B': 'Incorrect. x'}},
])
def test_invalid_result_requeues(root, changes):
    folder, rows = setup_rows(root)
    command(root, 'batches')
    write_result(folder, good(rows[0]) | changes)
    command(root, 'apply')
    row = store.read_jsonl(folder / 'bank.jsonl')[0]
    assert all(not c['explanation'] for c in row['choices'])
    manifest = store.read_json(folder / 'batches/explanations/manifest.json')
    assert manifest[-1]['attempt'] == 2 and manifest[-1]['items'] == [rows[0]['id']]


def test_fixture_input_matches_dispatch_shape():
    from pathlib import Path
    data = json.loads((Path(__file__).parent / 'fixtures/workers/explanations.in.json').read_text(encoding='utf-8'))
    assert data['step'] == 'explanations'
    assert set(data['questions'][0]) == {'id', 'question', 'choices', 'answer', 'explanations', 'explanation_blocks'}
