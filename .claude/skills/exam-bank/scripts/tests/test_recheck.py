import csv
import io
import os

import pytest

import export
import store
from test_batches import prepare
from test_eb_cli import run_eb

HEADER = ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at',
          'status', 'resolved_at', 'resolution']
REPORTED = '2026-11-10T09:00:00Z'
OLD = '2026-11-01T00:00:00Z'


def command(root, action, ok=True):
    result = run_eb(action, 'pmle', 'recheck', cwd=root)
    assert (result.returncode == 0) == ok, result.stderr
    return result.stdout if ok else result.stderr


def reports(root, rows, name='reports.csv', mtime=None, header=HEADER):
    folder = root / 'exam-bank/pmle/reports'
    folder.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, header, lineterminator='\r\n', extrasaction='ignore')
    writer.writeheader()
    for i, row in enumerate(rows):
        writer.writerow({'report_id': f'r{i}', 'reported_at': REPORTED, 'note': 'Looks wrong.',
                         'question_updated_at': '', 'status': 'open', 'resolved_at': '',
                         'resolution': ''} | row)
    path = folder / name
    path.write_text(buffer.getvalue(), encoding='utf-8', newline='')
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def bank(root, count=2):
    """Row 0 has an LLM answer A. Row 1 has a user answer A and user explanations."""
    folder = prepare(root, count=count)
    rows = store.read_jsonl(folder / 'bank.jsonl')
    for row in rows:
        row.update(subdomain='2.1', answer=['A'], answer_by='llm', uncertain=True,
                   answer_checked_at=OLD, updated_at=OLD, rechecked_at='', recheck_note='')
        row['choices'] = row['choices'][:2]
        for choice in row['choices']:
            choice.update(explanation=('Correct. Old.' if choice['letter'] == 'A' else 'Incorrect. Old.'),
                          explanation_by='llm')
    if count > 1:
        rows[1].update(answer_by='user')
        rows[1]['sources'][0].update(name='given', unsure=False)
        for choice in rows[1]['choices']:
            choice['explanation_by'] = 'user'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    return folder, rows


def write_result(folder, *results, name='recheck-0001'):
    store.write_atomic(folder / f'batches/recheck/{name}.json', store.dump_json(
        {'batch_id': name, 'step': 'recheck', 'results': list(results)}))


def good(row, **changes):
    return {'id': row['id'], 'status': 'ok', 'answer': ['A'], 'confidence': 'high',
            'note': 'The documentation agrees.', 'refs': ['https://cloud.google.com/docs'],
            'explanations': {}, 'why_conflicts': []} | changes


def after(folder, index=0):
    return store.read_jsonl(folder / 'bank.jsonl')[index]


def recheck_one(root, rows, folder, result):
    reports(root, [{'question_id': rows[0]['id']}])
    command(root, 'batches')
    write_result(folder, result)
    return command(root, 'apply')


def test_confirm_sets_check_and_note_and_keeps_updated_at(root):
    folder, rows = bank(root, 1)
    recheck_one(root, rows, folder, good(rows[0]))
    row = after(folder)
    assert row['recheck_note'] == 'Confirmed. The documentation agrees.'
    assert row['rechecked_at'] > REPORTED and row['answer_checked_at'] > OLD
    assert row['updated_at'] == OLD
    assert row['answer'] == ['A'] and row['answer_by'] == 'llm' and not row['uncertain']


def test_confirm_below_high_confidence_keeps_uncertain_and_rewrites_explanation(root):
    folder, rows = bank(root, 1)
    recheck_one(root, rows, folder, good(
        rows[0], confidence='medium', explanations={'B': 'Incorrect. A better reason.'}))
    row = after(folder)
    assert row['uncertain'] and row['choices'][1]['explanation'] == 'Incorrect. A better reason.'
    assert row['recheck_note'].startswith('Confirmed.') and row['updated_at'] > OLD


def test_confirm_on_a_source_row_makes_it_llm_and_on_a_user_row_keeps_user(root):
    folder, rows = bank(root)
    rows[0]['answer_by'] = 'source'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    reports(root, [{'question_id': r['id']} for r in rows])
    command(root, 'batches')
    write_result(folder, *[good(r) for r in rows])
    command(root, 'apply')
    assert [after(folder, i)['answer_by'] for i in (0, 1)] == ['llm', 'user']
    assert not after(folder, 1)['uncertain']


def test_overturn_changes_answer_and_non_user_explanations(root):
    folder, rows = bank(root, 1)
    recheck_one(root, rows, folder, good(rows[0], answer=['B'], explanations={
        'A': 'Incorrect. New A.', 'B': 'Correct. New B.'}))
    row = after(folder)
    assert row['answer'] == ['B'] and row['answer_by'] == 'llm' and row['uncertain']
    assert [c['explanation'] for c in row['choices']] == ['Incorrect. New A.', 'Correct. New B.']
    assert row['recheck_note'] == 'Changed from A to B. The documentation agrees.'
    assert row['updated_at'] > OLD


def test_unusable_retires_with_reason_in_note(root):
    folder, rows = bank(root, 1)
    recheck_one(root, rows, folder,
                {'id': rows[0]['id'], 'status': 'unusable', 'reason': 'Choice B is cut off.'})
    row = after(folder)
    assert row['status'] == 'retired' and row['updated_at'] == OLD
    assert row['recheck_note'] == 'Retired. Choice B is cut off.' and row['rechecked_at']


def test_user_row_with_different_llm_answer_is_kept_and_marked_uncertain(root):
    folder, rows = bank(root)
    reports(root, [{'question_id': rows[1]['id']}])
    command(root, 'batches')
    write_result(folder, good(rows[1], answer=['B'],
                              explanations={'A': 'Incorrect. X.', 'B': 'Correct. Y.'}))
    command(root, 'apply')
    row = after(folder, 1)
    assert row['answer'] == ['A'] and row['answer_by'] == 'user' and row['uncertain']
    assert [c['explanation'] for c in row['choices']] == [c['explanation'] for c in rows[1]['choices']]
    assert row['recheck_note'].startswith('Kept your answer A. The re-check suggests B.')
    assert row['updated_at'] == OLD and row['rechecked_at']


def test_user_explanation_survives_a_confirm_and_a_conflict_is_flagged(root):
    folder, rows = bank(root)
    reports(root, [{'question_id': rows[1]['id']}])
    command(root, 'batches')
    write_result(folder, good(rows[1], explanations={'A': 'Correct. Overwrite.'}, why_conflicts=['B']))
    command(root, 'apply')
    row = after(folder, 1)
    assert row['choices'][0]['explanation'] == 'Correct. Old.'
    assert row['uncertain'] and 'Your Why: on B contradicts' in row['answer_note']


def test_pending_filter_reads_newest_csv_by_header_and_lists_skips(root):
    folder, rows = bank(root, 4)
    rows[1]['rechecked_at'] = '2026-11-12T00:00:00Z'
    rows[2]['status'] = 'retired'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    reports(root, [{'question_id': rows[3]['id']}], name='old.csv', mtime=1_000_000_000)
    header = ['status', 'question_id', 'note', 'reported_at', 'report_id', 'question_updated_at',
              'resolved_at', 'resolution']
    reports(root, [
        {'question_id': rows[0]['id'], 'note': 'First.'},
        {'question_id': rows[1]['id']},
        {'question_id': rows[2]['id']},
        {'question_id': 'q_unknown00000'},
        {'question_id': rows[3]['id'], 'status': 'resolved'},
    ], name='new.csv', mtime=2_000_000_000, header=header)
    output = command(root, 'batches')
    assert 'skipped retired question: ' + rows[2]['id'] in output
    assert 'skipped unknown question: q_unknown00000' in output
    manifest = store.read_json(folder / 'batches/recheck/manifest.json')
    assert [e['items'] for e in manifest] == [[rows[0]['id']]]
    data = store.read_json(folder / 'batches/recheck/recheck-0001.in.json')
    assert data['step'] == 'recheck' and data['report_notes'] == {rows[0]['id']: 'First.'}
    assert [q['id'] for q in data['questions']] == [rows[0]['id']]
    assert set(data['source_answers']) == {rows[0]['id']}


def test_second_run_on_the_same_file_finds_nothing_and_apply_prints_the_close(root):
    folder, rows = bank(root, 1)
    closing = recheck_one(root, rows, folder, good(rows[0]))
    assert 'Next: /exam-bank pmle export' in closing and 'Import into the sheet:' in closing
    before = store.read_jsonl(folder / 'bank.jsonl')
    again = command(root, 'batches')
    assert 'dispatch:\n[]' in again
    assert len(store.read_json(folder / 'batches/recheck/manifest.json')) == 1
    command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl') == before


def test_note_is_one_line_and_capped_at_300_characters(root):
    folder, rows = bank(root, 1)
    recheck_one(root, rows, folder, good(rows[0], note='word ' * 120))
    note = after(folder)['recheck_note']
    assert len(note) == 300 and '\n' not in note


@pytest.mark.parametrize('changes', [{'note': 'Two\nlines'}, {'note': '<b>bold</b>'},
                                     {'note': 'see https://example.com/x'}])
def test_bad_note_requeues(root, changes):
    folder, rows = bank(root, 1)
    recheck_one(root, rows, folder, good(rows[0], **changes))
    assert not after(folder)['rechecked_at']
    assert store.read_json(folder / 'batches/recheck/manifest.json')[-1]['attempt'] == 2


def test_failed_batch_keeps_row_active_report_open_and_is_listed_in_state(root):
    folder, rows = bank(root, 1)
    reports(root, [{'question_id': rows[0]['id']}])
    command(root, 'batches')
    for attempt in (1, 2, 3):
        manifest = store.read_json(folder / 'batches/recheck/manifest.json')
        assert manifest[-1]['attempt'] == attempt
        write_result(folder, good(rows[0], answer=['Z']), name=manifest[-1]['batch_id'])
        command(root, 'apply')
    row = after(folder)
    assert row['status'] == 'active' and not row['rechecked_at'] and not row['recheck_note']
    state = run_eb('state', 'pmle', cwd=root).stdout
    assert 'recheck: total 3, done 2, pending 0, failed 1 (recheck-0003)' in state
    text = (folder / 'state.md').read_text(encoding='utf-8')
    assert 'recheck failed: recheck-0003' in text and rows[0]['id'] in text
    # A later invocation starts the question again at attempt 1.
    command(root, 'batches')
    assert store.read_json(folder / 'batches/recheck/manifest.json')[-1]['attempt'] == 1


def test_missing_reports_csv_or_column_stops_with_the_fix(root):
    bank(root, 1)
    assert 'No Reports CSV' in command(root, 'batches', ok=False)
    reports(root, [], header=['report_id', 'question_id'])
    assert 'lacks columns' in command(root, 'batches', ok=False)


def test_export_after_recheck_fills_columns_29_and_30(root):
    folder, rows = bank(root, 1)
    recheck_one(root, rows, folder, good(rows[0]))
    export.run(root, 'pmle', '2026-11-20T00:00:00Z')
    exported = list(csv.reader(io.StringIO(
        (folder / 'export/pmle-questions.csv').read_text(encoding='utf-8'), newline='')))
    header, cells = exported[0], exported[1]
    assert header[28:] == ['rechecked_at', 'recheck_note']
    assert cells[28] == after(folder)['rechecked_at'] and cells[29].startswith('Confirmed.')
