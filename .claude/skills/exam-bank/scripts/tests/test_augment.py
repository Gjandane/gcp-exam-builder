import json
import shutil

import pytest
import yaml

import augment
import store
from conftest import FIXTURES, SKILL
from test_eb_cli import run_eb

NOW = '2026-11-17T10:00:00Z'
CREATE_ID = 'augment-0001'
SETTINGS = {'target_total': 400, 'min_per_subdomain': 15, 'max_created_per_run': 100}


def eb(root, *argv):
    result = run_eb(*argv, cwd=root)
    assert result.returncode == 0, result.stderr
    return result.stdout


def make(root, **augment_settings):
    """A bank with checked rows in two Subdomains, and small augment settings."""
    path = root / 'exam-bank/config/models.yaml'
    shutil.copy(SKILL / 'templates/models.example.yaml', path)
    models = yaml.safe_load(path.read_text(encoding='utf-8'))
    models['augment'].update(target_total=20, min_per_subdomain=1, max_created_per_run=4)
    models['augment'].update(augment_settings)
    models['tasks']['augmentation']['batch_size'] = 2
    path.write_text(yaml.safe_dump(models), encoding='utf-8')
    folder = root / 'exam-bank/pmle'
    template = store.read_jsonl(FIXTURES / 'export/bank.jsonl')[0]
    rows = []
    for i, (subdomain, answer) in enumerate([('5.1', ['A']), ('5.1', ['B']), ('5.1', ['A', 'C']),
                                             ('2.1', ['A'])]):
        row = json.loads(json.dumps(template))
        row.update(id=f'q_{i:012x}', subdomain=subdomain, answer=answer, uncertain=False,
                   lineage='scraped', question=f'Stem number {i} about pipelines?',
                   answer_checked_at=NOW)
        row['choices'] = row['choices'][:4]
        rows.append(row)
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))
    return folder, rows


def config(root):
    return store.load_exam_config(root, 'pmle')


def fake_rows(counts):
    return [{'status': 'active', 'subdomain': sub} for sub, n in counts.items() for _ in range(n)]


def table(root, rows, **settings):
    return {e['subdomain']: e for e in augment.gap_table(config(root), rows, SETTINGS | settings)}


# Gap rule

def test_target_rounds_to_nearest_and_respects_floor(root):
    entries = table(root, [], max_created_per_run=10**6)
    # 400 * 13 / 101 / 2 = 25.74 -> 26; 400 * 21 / 101 / 3 = 27.72 -> 28; 400 * 16 / 101 / 3 = 21.1 -> 21
    assert entries['1.1']['target'] == 26 and entries['3.1']['target'] == 28
    assert entries['2.3']['target'] == 21
    floor = table(root, [], target_total=20, max_created_per_run=10**6)
    assert {e['target'] for e in floor.values()} == {15}


def test_half_rounds_up_and_exact_values_stay():
    sections = [{'number': 1, 'weight': 1, 'subdomains': [{'number': '1.1'}]},
                {'number': 2, 'weight': 1, 'subdomains': [{'number': '2.1'}]}]
    assert augment.targets({'sections': sections}, {'target_total': 5, 'min_per_subdomain': 0}) == {
        '1.1': 3, '2.1': 3}                                    # 2.5 rounds up, not to even
    assert augment.targets({'sections': sections}, {'target_total': 4, 'min_per_subdomain': 0}) == {
        '1.1': 2, '2.1': 2}


def test_gap_counts_active_rows_and_never_goes_negative(root):
    rows = fake_rows({'1.1': 40, '1.2': 5}) + [{'status': 'retired', 'subdomain': '1.2'}]
    entries = table(root, rows, max_created_per_run=10**6)
    assert entries['1.1']['gap'] == 0 and entries['1.1']['active'] == 40
    assert entries['1.2']['active'] == 5 and entries['1.2']['gap'] == 21


def test_created_rows_count_as_active(root):
    rows = fake_rows({'5.1': 3}) + [{'status': 'active', 'subdomain': '5.1', 'lineage': 'created'}]
    assert table(root, rows, max_created_per_run=10**6)['5.1']['active'] == 4


def test_scaling_uses_largest_remainder():
    assert augment.scale([10, 10, 10], 10) == [4, 3, 3]        # equal remainders, first wins
    assert augment.scale([7, 2, 1], 5) == [4, 1, 0]            # 3.5, 1.0, 0.5 -> remainders .5, 0, .5
    assert augment.scale([5, 5, 1], 3) == [2, 1, 0]            # 1.36, 1.36, 0.27: spare goes to the first
    assert augment.scale([3, 2], 10) == [3, 2]                 # under the cap: unchanged
    assert augment.scale([0, 0], 0) == [0, 0]


def test_planned_total_never_exceeds_the_cap(root):
    for cap in (0, 1, 7, 37, 99):
        entries = table(root, [], max_created_per_run=cap)
        assert sum(e['planned'] for e in entries.values()) == cap
        assert all(e['planned'] <= e['gap'] for e in entries.values())


# Plan command

def test_plan_prints_table_with_total_against_cap(root):
    make(root, max_created_per_run=4)
    out = eb(root, 'augment-plan', 'pmle')
    assert '| Subdomain | Active rows | Target | Planned new |' in out
    assert 'Total planned: 4 of max_created_per_run 4' in out
    assert 'opt_in: unset' in out


def test_plan_total_stays_within_cap_on_fixture_bank(root):
    make(root, target_total=400, min_per_subdomain=15, max_created_per_run=100)
    out = eb(root, 'augment-plan', 'pmle')
    planned = int(out.split('Total planned: ')[1].split(' ')[0])
    assert planned <= 100


def test_no_marks_step_skipped(root):
    folder, _ = make(root)
    eb(root, 'augment-plan', 'pmle', 'no')
    assert store.read_json(folder / 'state.json')['augment']['opt_in'] is False
    assert not (folder / 'batches/augment/manifest.json').exists()
    assert '- augment: skipped' in eb(root, 'state', 'pmle')


def test_yes_writes_create_batches_of_one_subdomain(root):
    folder, _ = make(root, max_created_per_run=5)
    eb(root, 'augment-plan', 'pmle', 'yes')
    manifest = store.read_json(folder / 'batches/augment/manifest.json')
    assert sum(e['items'][0]['count'] for e in manifest) == 5
    assert all(e['kind'] == 'create' and len(e['items']) == 1 and e['items'][0]['count'] <= 2
               for e in manifest)
    assert [e['batch_id'] for e in manifest] == [f'augment-{i:04d}' for i in range(1, len(manifest) + 1)]
    for entry in manifest:
        data = store.read_json(folder / 'batches/augment' / f'{entry["batch_id"]}.in.json')
        assert data['subdomain']['number'] == entry['items'][0]['subdomain']
        assert data['count'] == entry['items'][0]['count']
    assert store.read_json(folder / 'state.json')['augment']['opt_in'] is True


def test_create_input_holds_examples_stems_and_mix(root):
    folder, rows = make(root)
    entry = {'batch_id': 'augment-0001', 'items': [{'subdomain': '5.1', 'count': 2}]}
    first = augment.create_input(entry, rows, config(root))
    assert first == augment.create_input(entry, rows, config(root))     # seeded by the Batch id
    assert first['subdomain'] == {'number': '5.1', 'title': 'Developing end-to-end ML pipelines'}
    assert len(first['examples']) == 3 and {e['id'] for e in first['examples']} <= {r['id'] for r in rows}
    assert sorted(first['existing_stems']) == sorted(r['question'] for r in rows[:3])
    assert first['choice_count_mix'] == {'4': 3} and first['multi_select_share'] == 0.33
    assert all('derived_from' not in e for e in first['examples'])


def test_examples_skip_created_and_unchecked_uncertain_and_cap_at_five(root):
    folder, rows = make(root)
    more = []
    for i in range(10, 18):
        row = json.loads(json.dumps(rows[0]))
        row.update(id=f'q_{i:012x}', question=f'Another stem {i}?')
        more.append(row)
    more[0].update(lineage='created')
    more[1].update(uncertain=True, answer_checked_at='')
    more[2]['choices'][0]['explanation_by'] = 'source'
    bank = rows + more
    picked = augment.pick_examples(bank, config(root), '5.1', 'augment-0003')
    ids = [r['id'] for r in picked]
    assert len(ids) == 5 and more[0]['id'] not in ids and more[1]['id'] not in ids
    assert ids[0] == more[2]['id']                        # source explanations come first
    other = [r['id'] for r in augment.pick_examples(bank, config(root), '5.1', 'augment-0004')]
    assert set(other) != set(ids) or other != ids


def test_subdomain_without_examples_takes_its_section(root):
    folder, rows = make(root)
    picked = augment.pick_examples(rows, config(root), '2.2', 'augment-0001')
    assert [r['id'] for r in picked] == [rows[3]['id']]    # 2.1 is in the same Section


# Create validation

def creator(**changes):
    item = {'key': 'n1', 'status': 'ok', 'question': 'Which service orchestrates pipelines?',
            'choices': [{'text': 'Vertex AI Pipelines', 'explanation': 'Correct. It orchestrates runs.'},
                        {'text': 'Cloud DNS', 'explanation': 'Incorrect. It resolves names.'}],
            'answer': ['A'], 'subdomain': '5.1', 'derived_from': ['q_000000000000'],
            'confidence': 'high', 'note': 'Checked.', 'refs': ['https://cloud.google.com/vertex-ai/docs']}
    return item | changes


INPUT = {'subdomain': {'number': '5.1', 'title': 'x'}, 'count': 2, 'examples': [{'id': 'q_000000000000'}]}


def test_valid_create_passes():
    assert augment.check_create(creator(), INPUT) == ''


@pytest.mark.parametrize('changes', [
    {'choices': [{'text': 'Only one', 'explanation': 'Correct.'}]},
    {'choices': [{'text': str(i), 'explanation': 'Incorrect.'} for i in range(7)]},
    {'subdomain': '5.2'}, {'subdomain': ''},
    {'derived_from': ['q_unknown']}, {'derived_from': []}, {'derived_from': 'q_000000000000'},
    {'refs': []}, {'refs': ['https://example.com/docs']},
    {'answer': []}, {'answer': ['C']}, {'confidence': 'sure'},
    {'question': 'Use <b>bold</b> here'}, {'question': ''},
    {'choices': [{'text': 'A', 'explanation': 'Correct.'}, {'text': 'B', 'explanation': ''}]},
    {'note': 'two\nlines'},
    {'status': 'unusable', 'reason': ''},
])
def test_invalid_create_is_rejected(changes):
    assert augment.check_create(creator(**changes), INPUT) != ''


def test_choose_n_stem_needs_n_letters():
    item = creator(question='Select two services.')
    assert augment.check_create(item, INPUT) != ''
    assert augment.check_create(item | {'answer': ['A', 'B']}, INPUT) == ''


# Keep and drop

@pytest.mark.parametrize('creator_answer,verify_answer,verify_confidence,expected', [
    (['A'], ['A'], 'high', 'high'),
    (['A'], ['A'], 'medium', 'medium'),                # the lower of the two
    (['A'], ['A'], 'low', None),                       # low verify confidence drops
    (['A'], ['B'], 'high', None),                      # a differing answer drops
    (['A', 'B'], ['B', 'A'], 'high', 'high'),
    (['A', 'B'], ['A'], 'high', None),
])
def test_keep_and_drop(creator_answer, verify_answer, verify_confidence, expected):
    confidence, reason = augment.decide(
        {'answer': creator_answer, 'confidence': 'high'},
        {'status': 'ok', 'answer': verify_answer, 'confidence': verify_confidence})
    assert confidence == expected
    assert bool(reason) == (expected is None)


def test_kept_confidence_is_the_lower_of_the_two():
    assert augment.decide({'answer': ['A'], 'confidence': 'medium'},
                          {'status': 'ok', 'answer': ['A'], 'confidence': 'high'}) == ('medium', '')


def test_unusable_verify_drops():
    assert augment.decide({'answer': ['A'], 'confidence': 'high'},
                          {'status': 'unusable', 'reason': 'Broken.'})[0] is None


# Whole flow

def start(root, count=2, subdomain='5.1'):
    """A bank and one planned create Batch, as `augment-plan yes` would leave them."""
    folder, rows = make(root)
    entry = {'batch_id': CREATE_ID, 'kind': 'create', 'items': [{'subdomain': subdomain, 'count': count}],
             'attempt': 1, 'retry_of': None, 'created_at': NOW}
    store.write_atomic(folder / 'batches/augment/manifest.json', store.dump_json([entry]))
    store.write_atomic(folder / f'batches/augment/{CREATE_ID}.in.json',
                       store.dump_json(augment.create_input(entry, rows, config(root))))
    state = store.read_json(folder / 'state.json', {})
    state['augment'] = {'opt_in': True, 'asked_at': NOW}
    state['setup'] = {'passed_at': NOW}
    store.write_atomic(folder / 'state.json', store.dump_json(state))
    path = root / 'exam-bank/config/exams/pmle.yaml'
    path.write_text(path.read_text(encoding='utf-8').replace('enabled: true', 'enabled: false'), encoding='utf-8')
    store.write_atomic(folder / 'bank_meta.json', store.dump_json(
        {'schema_version': 1, 'exam': 'pmle', 'guide_version': config(root)['guide_version']}))
    return folder, rows


def write_result(folder, batch_id, results):
    store.write_atomic(folder / 'batches/augment' / f'{batch_id}.json',
                       store.dump_json({'batch_id': batch_id, 'step': 'augment', 'results': results}))


def verify_ok(ref, answer, confidence='high'):
    return {'id': ref, 'status': 'ok', 'answer': answer, 'confidence': confidence, 'note': 'Checked.',
            'refs': ['https://cloud.google.com/vertex-ai/docs'],
            'explanations': {'A': 'Correct. Yes.', 'B': 'Incorrect. No.'}, 'why_conflicts': []}


def test_flow_create_verify_keep_and_drop(root):
    folder, rows = start(root)
    out = eb(root, 'batches', 'pmle', 'augment')
    assert '"batch_id": "augment-0001"' in out and 'workers/augment.md' in out
    derived = [rows[0]['id']]
    write_result(folder, CREATE_ID, [
        creator(key='n1', derived_from=derived),
        creator(key='n2', question='Which service stores features?', derived_from=derived,
                confidence='medium'),
        creator(key='n3', status='unusable', reason='x'),     # beyond the count: ignored
    ])
    out = eb(root, 'apply', 'pmle', 'augment')
    manifest = store.read_json(folder / 'batches/augment/manifest.json')
    verifies = [e for e in manifest if e['kind'] == 'verify']
    assert [e['items'] for e in verifies] == [[f'{CREATE_ID}#n1'], [f'{CREATE_ID}#n2']]
    assert out.count('workers/answers.md') == 2
    blind = store.read_json(folder / 'batches/augment' / f'{verifies[0]["batch_id"]}.in.json')
    assert blind['source_answers'] == {}
    assert set(blind['questions'][0]) == {'id', 'question', 'choices'}
    assert all(set(c) == {'letter', 'text'} for c in blind['questions'][0]['choices'])

    write_result(folder, verifies[0]['batch_id'], [verify_ok(f'{CREATE_ID}#n1', ['A'])])
    write_result(folder, verifies[1]['batch_id'], [verify_ok(f'{CREATE_ID}#n2', ['B'])])
    out = eb(root, 'apply', 'pmle', 'augment')
    assert 'Questions: kept 1, dropped 1' in out and 'dispatch:\n[]' in out
    bank = {r['question']: r for r in store.read_jsonl(folder / 'bank.jsonl')}
    kept = bank['Which service orchestrates pipelines?']
    assert kept['lineage'] == 'created' and kept['derived_from'] == derived and kept['uncertain'] is False
    assert kept['answer'] == ['A'] and kept['answer_by'] == 'llm' and kept['answer_checked_at']
    assert kept['answer_confidence'] == 'high' and kept['explanation_by'] == 'llm'
    assert kept['subdomain'] == '5.1' and kept['subdomain_by'] == 'llm' and kept['status'] == 'active'
    assert kept['sources'][0]['name'] == 'created'
    assert kept['sources'][0]['url'] == f'batches/augment/{CREATE_ID}.json#n1'
    assert all(c['explanation'] and c['explanation_by'] == 'llm' for c in kept['choices'])
    assert 'Which service stores features?' not in bank
    assert len(store.read_jsonl(folder / 'sources/created.jsonl')) == 1

    # Applying again changes nothing, and drops are counted in state.md.
    before = (folder / 'bank.jsonl').read_bytes()
    eb(root, 'apply', 'pmle', 'augment')
    assert (folder / 'bank.jsonl').read_bytes() == before
    state = eb(root, 'state', 'pmle')
    assert '- augment: done' in state and '- augment drops: 1' in state
    for step in ('setup', 'scrape', 'llm-scrape', 'merge', 'tag', 'answers', 'explanations'):
        assert f'- {step}: ' + ('skipped' if step in ('scrape', 'llm-scrape') else 'done') in state
    assert 'Current step: export' in state
    assert store.read_json(folder / 'state.json')['merged']['sources/created.jsonl'] == store.sha256_file(
        folder / 'sources/created.jsonl')
    assert '- augment: total 3, done 3, pending 0, failed 0' in state


def test_kept_row_passes_export_checks(root):
    folder, rows = start(root, count=1)
    eb(root, 'batches', 'pmle', 'augment')
    write_result(folder, CREATE_ID, [creator(derived_from=[rows[0]['id']])])
    eb(root, 'apply', 'pmle', 'augment')
    verify = store.read_json(folder / 'batches/augment/manifest.json')[-1]
    write_result(folder, verify['batch_id'], [verify_ok(verify['items'][0], ['A'], 'medium')])
    eb(root, 'apply', 'pmle', 'augment')
    row = next(r for r in store.read_jsonl(folder / 'bank.jsonl') if r['lineage'] == 'created')
    assert row['answer_confidence'] == 'medium' and row['answer'] and row['subdomain']
    assert all(c['explanation'] for c in row['choices'])
    assert 'active' in eb(root, 'export', 'pmle')                   # export does not refuse


def test_invalid_create_requeues_only_the_missing_questions(root):
    folder, rows = start(root, count=2)
    eb(root, 'batches', 'pmle', 'augment')
    write_result(folder, CREATE_ID, [creator(derived_from=[rows[0]['id']]), creator(key='n2', refs=[])])
    eb(root, 'apply', 'pmle', 'augment')
    manifest = store.read_json(folder / 'batches/augment/manifest.json')
    retry = [e for e in manifest if e['kind'] == 'create' and e['attempt'] == 2]
    assert len(retry) == 1 and retry[0]['retry_of'] == CREATE_ID and retry[0]['items'][0]['count'] == 1
    assert sum(e['kind'] == 'verify' for e in manifest) == 1


def test_failed_create_restarts_at_attempt_one_on_next_run(root):
    folder, rows = start(root, count=2)
    for _ in range(3):
        eb(root, 'batches', 'pmle', 'augment')
        last = store.read_json(folder / 'batches/augment/manifest.json')[-1]
        write_result(folder, last['batch_id'], [])
        eb(root, 'apply', 'pmle', 'augment')
    manifest = store.read_json(folder / 'batches/augment/manifest.json')
    assert [e['attempt'] for e in manifest] == [1, 2, 3]
    assert any(f'- augment: {name}' in eb(root, 'state', 'pmle') for name in ('pending', 'in progress'))
    eb(root, 'batches', 'pmle', 'augment')
    manifest = store.read_json(folder / 'batches/augment/manifest.json')
    assert manifest[-1]['attempt'] == 1 and manifest[-1]['retry_of'] == manifest[-2]['batch_id']
    assert manifest[-1]['items'][0]['count'] == 2


def test_open_plan_stays_fixed(root):
    folder, rows = start(root, count=2)
    assert 'A plan is open' in eb(root, 'augment-plan', 'pmle')
    assert 'stays fixed' in eb(root, 'augment-plan', 'pmle', 'yes')
    assert len(store.read_json(folder / 'batches/augment/manifest.json')) == 1


def test_forced_plan_after_done_plans_new_gaps(root):
    folder, rows = start(root, count=1)
    eb(root, 'batches', 'pmle', 'augment')
    write_result(folder, CREATE_ID, [creator(status='unusable', reason='Nothing left.')])
    eb(root, 'apply', 'pmle', 'augment')
    assert '- augment: done' in eb(root, 'state', 'pmle')
    out = eb(root, 'augment-plan', 'pmle')
    assert 'A plan is open' not in out
    eb(root, 'augment-plan', 'pmle', 'yes')
    assert len(store.read_json(folder / 'batches/augment/manifest.json')) > 1


def test_verify_result_with_bad_text_is_rejected_and_requeued(root):
    folder, rows = start(root, count=1)
    eb(root, 'batches', 'pmle', 'augment')
    write_result(folder, CREATE_ID, [creator(derived_from=[rows[0]['id']])])
    eb(root, 'apply', 'pmle', 'augment')
    verify = store.read_json(folder / 'batches/augment/manifest.json')[-1]
    bad = verify_ok(verify['items'][0], ['A']) | {'explanations': {'A': '<b>x</b>', 'B': 'Incorrect. No.'}}
    write_result(folder, verify['batch_id'], [bad])
    eb(root, 'apply', 'pmle', 'augment')
    last = store.read_json(folder / 'batches/augment/manifest.json')[-1]
    assert last['kind'] == 'verify' and last['attempt'] == 2 and last['items'] == verify['items']
    assert not (folder / 'sources/created.jsonl').exists()
