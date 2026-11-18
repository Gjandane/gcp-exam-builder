import pathlib
import shutil

import pytest
import yaml

import store
import study_guide
from conftest import FIXTURES, SKILL
from test_eb_cli import run_eb


NOW = '2026-11-18T00:00:00Z'
LATER = '2026-11-18T01:00:00Z'
TITLE = 'Exploring and preprocessing data for ML'
CHAPTER = '2.1-exploring-and-preprocessing-data-for-ml.md'


def row(number=1, **changes):
    return {
        'id': f'q_{number:012x}', 'exam': 'pmle', 'status': 'active',
        'subdomain': '2.1', 'subdomain_by': 'user',
        'subdomain_confidence': 'high', 'answer_confidence': 'high',
        'question': 'Which preparation method prevents a feature mismatch?',
        'choices': [
            {'letter': 'A', 'text': 'Share transformation logic.',
             'explanation': 'Correct. Both environments compute matching features.',
             'explanation_by': 'llm'},
            {'letter': 'B', 'text': 'Change the model schedule.',
             'explanation': 'Incorrect. Scheduling does not alter feature values.',
             'explanation_by': 'llm'},
        ],
        'answer': ['A'], 'answer_by': 'llm', 'answer_checked_at': NOW,
        'explanation_by': 'llm', 'lineage': 'given', 'sources': [],
        'uncertain': False, 'updated_at': '2026-11-17T08:00:00Z',
    } | changes


def prepare(root, rows=None, cap=80):
    config_path = root / 'exam-bank/config/models.yaml'
    shutil.copy(SKILL / 'templates/models.example.yaml', config_path)
    config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    config['study_guide']['max_questions'] = cap
    config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
    folder = root / 'exam-bank/pmle'
    save_rows(folder, [row()] if rows is None else rows)
    return folder


def save_rows(folder, rows):
    store.write_atomic(folder / 'bank.jsonl', store.dump_jsonl(rows))


def input_data(folder, subdomain='2.1'):
    return store.read_json(folder / f'batches/study-guide/{subdomain}.in.json')


def index_line(folder, subdomain='2.1'):
    return next(line for line in (folder / 'study_guide_state.md').read_text(
        encoding='utf-8').splitlines() if line.startswith(('- [ ] ' + subdomain + ' ',
                                                          '- [x] ' + subdomain + ' ')))


def chapter_path(folder):
    return folder / 'study-guide' / CHAPTER


def write_chapter(folder, text=None):
    if text is None:
        text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    store.write_atomic(chapter_path(folder), text.encode('utf-8'))


def planned(root):
    folder = prepare(root)
    study_guide.plan(root, 'pmle', NOW, '2.1')
    return folder


def test_plan_selects_first_ready_in_guide_order_and_rebuilds_index(root):
    rows = [row(1, subdomain='2.1'), row(2, subdomain='1.2'),
            row(3, subdomain='1.1', answer=[], answer_checked_at='')]
    folder = prepare(root, rows)
    (folder / 'study_guide_state.md').write_text('stale index', encoding='utf-8')

    output = study_guide.plan(root, 'pmle', NOW)

    assert input_data(folder, '1.2')['subdomain'] == '1.2'
    assert '1.2' in output and 'exam-bank-researcher' in output
    assert 'sonnet' in output and 'medium' in output
    assert '1 pending answers' in index_line(folder, '1.1')
    assert 'ready' in index_line(folder)
    assert '1 Qs' in index_line(folder)
    assert '`/exam-bank pmle study-guide 2.1`' in index_line(folder)
    assert not (folder / 'batches/study-guide/manifest.json').exists()


@pytest.mark.parametrize('changes,reason', [
    ({'answer': [], 'answer_checked_at': ''}, 'pending answers'),
    ({'uncertain': True, 'answer_checked_at': ''}, 'pending answers'),
    ({'choices': [dict(c, explanation='') for c in row()['choices']]},
     'pending explanations'),
])
def test_named_blocked_subdomain_stops_with_reason_and_count(root, changes, reason):
    folder = prepare(root, [row(1, **changes), row(2, **changes)])

    with pytest.raises(store.Stop, match=reason):
        study_guide.plan(root, 'pmle', NOW, '2.1')

    assert f'2 {reason}' in index_line(folder)
    assert not (folder / 'batches/study-guide/2.1.in.json').exists()


def test_untagged_active_rows_block_until_their_subdomain_is_known(root):
    folder = prepare(root, [row(1), row(2, subdomain=''),
                            row(3, subdomain='', status='retired')])
    with pytest.raises(store.Stop, match='pending tag'):
        study_guide.plan(root, 'pmle', NOW, '2.1')
    assert '1 pending tag' in index_line(folder)


def test_named_selection_uses_exact_title_slug_and_all_lineages(root):
    rows = [row(1), row(2, lineage='scraped'), row(3, lineage='created'),
            row(4, status='retired')]
    folder = prepare(root, rows)

    study_guide.plan(root, 'pmle', NOW, '2.1')

    data = input_data(folder)
    assert data['active_ids'] == [r['id'] for r in rows[:3]]
    assert [q['id'] for q in data['questions']] == data['active_ids']
    assert data['title'] == TITLE
    assert pathlib.Path(data['chapter_path']).name == CHAPTER
    assert 'study-guide' in data['chapter_path']
    for source, fed in zip(rows, data['questions']):
        assert fed['choices'] == source['choices']
        assert fed['answer'] == source['answer']


def test_input_marks_uncertain_answer_and_low_confidence_rows(root):
    folder = prepare(root, [row(1), row(2, uncertain=True),
                            row(3, answer_confidence='low'),
                            row(4, subdomain_confidence='low')])
    study_guide.plan(root, 'pmle', NOW, '2.1')
    assert [q['marked'] for q in input_data(folder)['questions']] == [False, True, True, True]


def test_seeded_sample_keeps_full_ids_and_prefers_non_created(root):
    rows = [row(i, lineage='created' if i < 6 else 'scraped') for i in range(1, 11)]
    folder = prepare(root, rows, cap=3)

    study_guide.plan(root, 'pmle', NOW, '2.1')
    first = input_data(folder)
    study_guide.plan(root, 'pmle', LATER, '2.1')
    second = input_data(folder)

    assert first['active_ids'] == [r['id'] for r in rows]
    assert len(first['questions']) == 3
    assert all(q['lineage'] != 'created' for q in first['questions'])
    assert first['questions'] == second['questions']
    assert '3 of 10 Qs' in index_line(folder)


def test_sample_uses_created_rows_when_needed_to_fill_cap(root):
    folder = prepare(root, [row(1), row(2, lineage='created'),
                            row(3, lineage='created')], cap=2)
    study_guide.plan(root, 'pmle', NOW, '2.1')
    data = input_data(folder)
    assert len(data['questions']) == 2
    assert data['questions'][0]['id'] == row(1)['id']


def test_check_passes_good_fixture_and_rebuilds_done_index(root):
    folder = planned(root)
    write_chapter(folder)

    output = study_guide.check(root, 'pmle', NOW, '2.1')

    assert 'done' in output.lower() or 'pass' in output.lower()
    assert chapter_path(folder).exists()
    assert '| done' in index_line(folder)
    assert index_line(folder).startswith('- [x]')


def test_existing_chapter_requires_redo_without_overwriting_its_input(root):
    folder = planned(root)
    write_chapter(folder)
    study_guide.check(root, 'pmle', NOW, '2.1')
    old_input = (folder / 'batches/study-guide/2.1.in.json').read_bytes()

    with pytest.raises(store.Stop, match='redo'):
        study_guide.plan(root, 'pmle', LATER, '2.1')

    assert (folder / 'batches/study-guide/2.1.in.json').read_bytes() == old_input
    study_guide.plan(root, 'pmle', LATER, '2.1', redo=True)
    assert input_data(folder)['subdomain'] == '2.1'


@pytest.mark.parametrize('change', ['added', 'removed', 'updated'])
def test_existing_chapter_becomes_stale_when_active_ids_or_rows_change(root, change):
    folder = planned(root)
    write_chapter(folder)
    study_guide.check(root, 'pmle', NOW, '2.1')
    rows = store.read_jsonl(folder / 'bank.jsonl')
    if change == 'added':
        rows.append(row(2))
    elif change == 'removed':
        rows[0]['status'] = 'retired'
    else:
        rows[0]['updated_at'] = LATER
    save_rows(folder, rows)
    with pytest.raises(store.Stop):
        study_guide.plan(root, 'pmle', LATER, '2.1')
    assert 'stale:' in index_line(folder)
    assert '`/exam-bank pmle study-guide 2.1 redo`' in index_line(folder)


def test_unsampled_row_update_also_makes_chapter_stale(root):
    folder = prepare(root, [row(1), row(2)], cap=1)
    study_guide.plan(root, 'pmle', NOW, '2.1')
    data = input_data(folder)
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    text = text.replace('q_000000000001', data['questions'][0]['id'])
    write_chapter(folder, text)
    study_guide.check(root, 'pmle', NOW, '2.1')
    rows = store.read_jsonl(folder / 'bank.jsonl')
    next(r for r in rows if r['id'] != data['questions'][0]['id'])['updated_at'] = LATER
    save_rows(folder, rows)
    with pytest.raises(store.Stop):
        study_guide.plan(root, 'pmle', LATER, '2.1')
    assert 'stale:' in index_line(folder)


def mutate_header(text, key, value):
    _, front, body = text.split('---', 2)
    header = yaml.safe_load(front)
    if value is None:
        header.pop(key)
    else:
        header[key] = value
    return '---\n' + yaml.safe_dump(header, sort_keys=False) + '---' + body


@pytest.mark.parametrize('field,value', [
    ('exam', 'other'), ('subdomain', '1.1'), ('subdomain', 2.1),
    ('title', 'Wrong title'), ('guide_version', 'old'),
    ('question_ids', ['q_ffffffffffff']), ('question_ids', []),
    ('question_ids', ['q_000000000001', 'q_000000000001']),
    ('written_at', 'yesterday'), ('written_at', '2026-11-17T00:00:00Z'),
    ('model', ''),
] + [(field, None) for field in ('exam', 'subdomain', 'title', 'guide_version',
                                  'question_ids', 'written_at', 'model')])
def test_check_rejects_wrong_or_missing_frontmatter(root, field, value):
    folder = planned(root)
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    assert_rejected(folder, mutate_header(text, field, value), root)


def assert_rejected(folder, text, root):
    write_chapter(folder, text)
    with pytest.raises(store.Stop):
        study_guide.check(root, 'pmle', NOW, '2.1')
    assert not chapter_path(folder).exists()
    assert '| ready' in index_line(folder)


@pytest.mark.parametrize('mutation', [
    lambda t: t.split('---', 2)[2],
    lambda t: t.replace('title:', 'title: [', 1),
    lambda t: t.replace('## Traps\n', ''),
    lambda t: t.replace('## Scope\n', '## Traps\n', 1),
    lambda t: t.replace('## Scope\n', '## Key concepts\n', 1),
    lambda t: t + '\nUnknown evidence q_ffffffffffff.\n',
    lambda t: t.replace('https://cloud.google.com', 'http://cloud.google.com'),
    lambda t: t + '\nhttps://cloud.google.com.evil.example/docs\n',
    lambda t: t + '\nhttps://example.com/reference\n',
    lambda t: t + '\n[Relative external link](//example.com/reference)\n',
    lambda t: t + '\n' + 'Additional material. ' * 2000,
    lambda t: t[:t.index('## Scope')] + '## Scope\nToo short.\n',
])
def test_check_rejects_each_chapter_rule(root, mutation):
    folder = planned(root)
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    assert_rejected(folder, mutation(text), root)


def test_check_rejects_bad_fixture_chapter(root):
    folder = planned(root)
    assert_rejected(folder, (FIXTURES / 'study-guide/bad.md').read_text(
        encoding='utf-8'), root)


@pytest.mark.parametrize('link', [
    '<a href="//example.com/docs">Reference</a>',
    "<a href='javascript:alert(1)'>Reference</a>",
    '<img src="http://cloud.google.com/image.png">',
    "<img src='https://example.com/image.png'>",
    '<//example.com/docs>',
])
def test_check_rejects_non_documentation_html_links_and_autolinks(root, link):
    folder = planned(root)
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    assert_rejected(folder, text + '\n' + link + '\n', root)


@pytest.mark.parametrize('field', ['question', 'choice'])
def test_check_rejects_normalized_twelve_word_copy_from_input(root, field):
    source = 'Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu.'
    question = row()
    if field == 'question':
        question['question'] = source
    else:
        question['choices'][0]['text'] = source
    folder = prepare(root, [question])
    study_guide.plan(root, 'pmle', NOW, '2.1')
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    copied = 'ALPHA, beta GAMMA delta epsilon zeta eta theta iota kappa lambda mu'
    assert_rejected(folder, text + '\n' + copied + '\n', root)


def test_check_allows_eleven_shared_words(root):
    source = 'Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu.'
    folder = prepare(root, [row(question=source)])
    study_guide.plan(root, 'pmle', NOW, '2.1')
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    write_chapter(folder, text + '\nAlpha beta gamma delta epsilon zeta eta theta iota kappa lambda.\n')
    study_guide.check(root, 'pmle', NOW, '2.1')
    assert chapter_path(folder).exists()


def test_cli_plan_and_check_are_connected(root):
    folder = prepare(root)
    plan = run_eb('study-guide-plan', 'pmle', '2.1', cwd=root)
    assert plan.returncode == 0, plan.stderr
    assert input_data(folder)['subdomain'] == '2.1'
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    text = mutate_header(text, 'written_at', input_data(folder)['written_at'])
    write_chapter(folder, text)
    checked = run_eb('study-guide-check', 'pmle', '2.1', cwd=root)
    assert checked.returncode == 0, checked.stderr
    assert '| done' in index_line(folder)


def test_worker_fixture_is_complete_and_manually_usable():
    data = store.read_json(FIXTURES / 'workers/study-guide.in.json')
    assert data['active_ids'] == [q['id'] for q in data['questions']]
    assert all('marked' in q and q['choices'] and q['answer'] for q in data['questions'])
    assert data['chapter_path'].endswith(CHAPTER)



@pytest.mark.parametrize('metadata', ["written_at: '2026-11-18T00:00:00Z'", '[]', 'null'])
def test_unfinished_chapter_never_appears_done(root, metadata):
    folder = planned(root)
    write_chapter(folder, '---\n' + metadata + '\n---\n')
    with pytest.raises(store.Stop, match='redo'):
        study_guide.plan(root, 'pmle', NOW, '2.1')
    assert 'stale: invalid' in index_line(folder)
    assert not index_line(folder).startswith('- [x]')


def test_check_rejects_non_https_autolink(root):
    folder = planned(root)
    text = (FIXTURES / 'study-guide/good.md').read_text(encoding='utf-8')
    write_chapter(folder, text + '\n<mailto:person@example.com>\n')
    with pytest.raises(store.Stop):
        study_guide.check(root, 'pmle', NOW, '2.1')
    assert not chapter_path(folder).exists()
