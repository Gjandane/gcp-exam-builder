import pytest
import store
from test_batches import prepare
from test_eb_cli import run_eb


def command(root, action):
    result = run_eb(action, 'pmle', 'answers', cwd=root)
    assert result.returncode == 0, result.stderr
    return result.stdout


def setup_rows(root, count=1):
    folder = prepare(root, count=count)
    rows = store.read_jsonl(folder / 'bank.jsonl')
    for row in rows:
        row.update(answer=[], answer_by='', answer_checked_at='', uncertain=False)
        for choice in row['choices']:
            choice.update(explanation='', explanation_by='')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    return folder, rows


def write_result(folder, result):
    path = folder / 'batches/answers/answers-0001.json'
    store.write_atomic(path, store.dump_json({'batch_id': 'answers-0001', 'step': 'answers', 'results': [result]}))


def test_answers_batch_and_apply(root):
    folder, rows = setup_rows(root, 2)
    rows[1].update(answer=['A'], answer_checked_at='2026-01-01T00:00:00Z')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    manifest = store.read_json(folder / 'batches/answers/manifest.json')
    assert manifest[0]['items'] == [rows[0]['id']]
    input_data = store.read_json(folder / 'batches/answers/answers-0001.in.json')
    assert all(set(c) == {'letter', 'text'} for c in input_data['questions'][0]['choices'])
    explanations = {c['letter']: 'Correct. A fact.' for c in rows[0]['choices']}
    write_result(folder, {'id': rows[0]['id'], 'status': 'ok', 'answer': ['A'],
                          'confidence': 'low', 'note': 'Checked.', 'refs': [],
                          'explanations': explanations, 'why_conflicts': []})
    command(root, 'apply')
    row = store.read_jsonl(folder / 'bank.jsonl')[0]
    assert row['answer'] == ['A'] and row['answer_by'] == 'llm'
    assert row['uncertain'] and row['answer_checked_at'] and row['updated_at']


def good(row, **changes):
    return {'id': row['id'], 'status': 'ok', 'answer': ['A'], 'confidence': 'high',
            'note': 'Checked.', 'refs': ['https://docs.cloud.google.com/dataflow/docs'],
            'explanations': {c['letter']: 'Incorrect. A fact.' for c in row['choices']},
            'why_conflicts': []} | changes


@pytest.mark.parametrize('changes', [
    {'answer': []}, {'answer': ['Z']}, {'answer': ['A', 'A']},
    {'confidence': 'certain'}, {'refs': ['https://evilcloud.google.com/docs']},
    {'refs': ['http://cloud.google.com/docs']}, {'explanations': {}},
    {'explanations': {'A': '<b>Bad</b>'}}, {'why_conflicts': ['A']},
    {'note': 'See HTTPS://example.com/docs'},
    {'explanations': {'A': 'Incorrect. FTP://example.com/docs'}},
    {'status': 'unusable', 'reason': ''},
])
def test_invalid_result_requeues(root, changes):
    folder, rows = setup_rows(root)
    command(root, 'batches')
    write_result(folder, good(rows[0], **changes))
    command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['answer'] == []
    manifest = store.read_json(folder / 'batches/answers/manifest.json')
    assert manifest[-1]['attempt'] == 2 and manifest[-1]['items'] == [rows[0]['id']]


@pytest.mark.parametrize('answer,accepted', [(['A'], False), (['A', 'B'], True)])
def test_choose_two_requires_two_letters(root, answer, accepted):
    folder, rows = setup_rows(root)
    rows[0]['question'] = 'Select two options.'
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    write_result(folder, good(rows[0], answer=answer))
    command(root, 'apply')
    assert bool(store.read_jsonl(folder / 'bank.jsonl')[0]['answer']) == accepted


@pytest.mark.parametrize('stem', ['Select eleven.', 'Choose one hundred.'])
def test_impossible_written_count_is_rejected(root, stem):
    folder, rows = setup_rows(root)
    rows[0]['question'] = stem
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    write_result(folder, good(rows[0]))
    command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['answer'] == []


@pytest.mark.parametrize('unsure', [False, True])
def test_user_ticks_and_why_survive(root, unsure):
    folder, rows = setup_rows(root)
    row = rows[0]
    row.update(answer=['B'], answer_by='user', uncertain=True)
    row['sources'][0].update(name='given', unsure=unsure)
    row['choices'][0].update(explanation='**My Why.**', explanation_by='user')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    result = good(row, why_conflicts=['A'])
    result['explanations']['A'] = '<b>Discard this</b>'
    write_result(folder, result)
    command(root, 'apply')
    updated = store.read_jsonl(folder / 'bank.jsonl')[0]
    assert updated['answer'] == (['A'] if unsure else ['B'])
    assert updated['answer_by'] == ('llm' if unsure else 'user')
    assert updated['choices'][0]['explanation'] == '**My Why.**'
    assert updated['uncertain'] and 'Your Why: on A' in updated['answer_note']
    if not unsure:
        assert 'LLM answer: A' in updated['answer_note']
        assert all(not c['explanation'] for c in updated['choices'][1:])


def test_unusable_retires_and_records_reason(root):
    folder, rows = setup_rows(root)
    command(root, 'batches')
    write_result(folder, {'id': rows[0]['id'], 'status': 'unusable', 'reason': 'Missing choice.'})
    command(root, 'apply')
    assert store.read_jsonl(folder / 'bank.jsonl')[0]['status'] == 'retired'
    assert store.read_jsonl(folder / 'log.jsonl')[0]['reason'] == 'Missing choice.'


def test_input_separates_answers_and_explanations_from_blind_questions(root):
    folder, rows = setup_rows(root)
    row = rows[0]
    row.update(answer=['B'], answer_by='source', uncertain=True)
    row['choices'][0].update(explanation='Source explanation', explanation_by='source')
    row['sources'][0].update(name='example', site_answer=['B'], community_answer=['A'],
                             explanation_block='Source block')
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    command(root, 'batches')
    data = store.read_json(folder / 'batches/answers/answers-0001.in.json')
    assert data['questions'] == [{'id': row['id'], 'question': row['question'],
                                  'choices': [{'letter': c['letter'], 'text': c['text']}
                                              for c in row['choices']]}]
    assert data['source_answers'][row['id']] == {
        'stored': ['B'], 'sources': [{'name': 'example', 'answer': ['B']},
                                     {'name': 'example-community', 'answer': ['A']}],
        'explanations': {'A': {'text': 'Source explanation', 'by': 'source'}},
        'explanation_blocks': ['Source block']}
