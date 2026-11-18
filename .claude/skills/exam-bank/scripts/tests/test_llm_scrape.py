import shutil

import pytest
import yaml

import batches
import fetch
import llm_scrape
import store
from conftest import FIXTURES, SKILL
from ids import norm
from test_eb_cli import run_eb

PAGE = (FIXTURES / 'workers/llm-scrape.page.txt').read_text(encoding='utf-8')
HTML = '<html><body><p>' + PAGE.replace('\n', '<br>') + '</p></body></html>'
ROBOTS_OK = 'User-agent: *\nAllow: /\n'
NOW = '2026-11-17T10:00:00Z'
CHANGED = HTML.replace('Question 3', 'Question 3 (revised)')


class Answer:
    def __init__(self, status=200, text=''):
        self.status_code, self.text, self.content = status, text, text.encode('utf-8')


def getter(pages, robots=ROBOTS_OK, calls=None):
    def get(url, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, headers))
        if url.endswith('/robots.txt'):
            return Answer(200, robots) if robots is not None else Answer(404)
        value = pages[url]
        return value() if callable(value) else value
    return get


def setup_root(root, enabled=('whizlabs',)):
    path = root / 'exam-bank/config/exams/pmle.yaml'
    config = yaml.safe_load(path.read_text(encoding='utf-8'))
    for source in config['llm_sources']:
        source['enabled'] = source['name'] in enabled
    path.write_text(yaml.safe_dump(config), encoding='utf-8')
    shutil.copy(SKILL / 'templates/models.example.yaml', root / 'exam-bank/config/models.yaml')
    return config


def url_of(config, name='whizlabs'):
    return next(s for s in config['llm_sources'] if s['name'] == name)['urls'][0]


def meta(root, name='whizlabs'):
    return store.read_json(root / f'exam-bank/pmle/raw/{name}/01.meta.json')


def do_fetch(root, config, pages, now=NOW, **kw):
    return fetch.run(root, 'pmle', now, get=getter(pages, **kw), config=config)


# Fetch

def test_fetch_saves_html_text_meta_with_user_agent(root):
    config = setup_root(root)
    url, calls = url_of(config), []
    do_fetch(root, config, {url: Answer(200, HTML)}, calls=calls)
    base = root / 'exam-bank/pmle/raw/whizlabs/01'
    assert base.with_suffix('.html').read_text(encoding='utf-8') == HTML
    assert 'Spot VMs use spare capacity' in base.with_suffix('.txt').read_text(encoding='utf-8')
    saved = meta(root)
    assert saved['status'] == 'ok' and saved['url'] == url and len(saved['sha256_txt']) == 64
    assert calls and all(h == {'User-Agent': 'Mozilla/5.0 (compatible; exam-bank)'} for _, h in calls)


def test_fetch_failure_reasons_each_leave_a_meta_file(root):
    config = setup_root(root)
    url = url_of(config)
    do_fetch(root, config, {url: Answer(200, HTML)}, robots='User-agent: *\nDisallow: /\n')
    assert meta(root)['status'] == 'failed: robots'
    do_fetch(root, config, {url: Answer(503)})
    assert meta(root)['status'] == 'failed: http 503'

    def boom():
        raise ConnectionError('down')
    do_fetch(root, config, {url: boom})
    assert meta(root)['status'] == 'failed: network ConnectionError'
    do_fetch(root, config, {url: Answer(200, '<body>' + 'x ' * 80000 + '</body>')})
    assert meta(root)['status'] == 'failed: too large'


def test_unchanged_page_with_valid_result_is_skipped_and_failed_page_is_fetched_again(root):
    config = setup_root(root)
    url = url_of(config)
    do_fetch(root, config, {url: Answer(200, HTML)})
    path = root / 'exam-bank/pmle/raw/whizlabs/01.meta.json'
    saved = meta(root) | {'applied': 'llm-scrape-0001'}
    store.write_atomic(path, store.dump_json(saved))
    do_fetch(root, config, {url: Answer(200, HTML)}, now='2027-01-01T00:00:00Z')
    assert meta(root) == saved                       # untouched, not queued again
    do_fetch(root, config, {url: Answer(200, CHANGED)})
    assert 'applied' not in meta(root)               # changed text, fresh meta
    store.write_atomic(path, store.dump_json(meta(root) | {'status': 'failed: no questions'}))
    do_fetch(root, config, {url: Answer(200, HTML)})
    assert meta(root)['status'] == 'ok'              # failed before, fetched again


# Validation

def question(**changes):
    return {'n': 1, 'status': 'ok',
            'question': 'Which Google Cloud service runs a managed Apache Beam pipeline?',
            'choices': ['Dataflow', 'Cloud Storage'], 'answer': ['A'],
            'explanations': {'block': 'Dataflow is the managed runner for Apache Beam.'},
            'subdomain_label': ''} | changes


@pytest.mark.parametrize('changes, reason', [
    ({}, ''),
    ({'question': 'Which Google Cloud service runs a managed Beam pipeline?'}, 'stem'),
    ({'choices': ['Dataflow', 'Cloud Storages']}, 'choice not found'),
    ({'explanations': {'A': 'Dataflow is a managed runner for Apache Beam.'}}, 'explanation not found'),
    ({'answer': ['C']}, 'answer letters'),
    ({'answer': ['A', 'A']}, 'answer letters'),
    ({'explanations': {'C': 'Dataflow is the managed runner for Apache Beam.'}}, 'letter'),
    ({'choices': ['Dataflow']}, '2 to 6'),
    ({'question': '<b>Which Google Cloud service runs a managed Apache Beam pipeline?</b>'}, 'cell text'),
])
def test_check_question(changes, reason):
    got = llm_scrape.check_question(question(**changes), norm(PAGE))
    assert (got == '') if not reason else reason in got.lower()


def test_typo_is_kept_and_a_fixed_typo_is_rejected():
    typo = question(question='Wich option is cheaper for fault-tolerant batch work?',
                    choices=['On-demand VMs', 'Spot VMs', 'Sole-tenant nodes'])
    assert llm_scrape.check_question(typo, norm(PAGE)) == ''
    fixed = typo | {'question': 'Which option is cheaper for fault-tolerant batch work?'}
    assert 'stem' in llm_scrape.check_question(fixed, norm(PAGE)).lower()


# Batches and apply

def form(root, config, html=HTML, now=NOW):
    task, cfg, options = batches.configuration(root, 'pmle', 'llm-scrape')
    return llm_scrape.run(root, 'pmle', now, task, cfg, options,
                          get=getter({url_of(config): Answer(200, html)}))


def write_result(root, batch_id, results):
    path = root / f'exam-bank/pmle/batches/llm-scrape/{batch_id}.json'
    store.write_atomic(path, store.dump_json(
        {'batch_id': batch_id, 'step': 'llm-scrape', 'results': results}))


def apply(root):
    result = run_eb('apply', 'pmle', 'llm-scrape', cwd=root)
    assert result.returncode == 0, result.stderr
    return result.stdout


def manifest(root):
    return store.read_json(root / 'exam-bank/pmle/batches/llm-scrape/manifest.json', [])


def second_question():
    return {'n': 2, 'status': 'ok', 'question': 'Wich option is cheaper for fault-tolerant batch work?',
            'choices': ['On-demand VMs', 'Spot VMs', 'Sole-tenant nodes'], 'answer': [],
            'explanations': {'block': 'Spot VMs use spare capacity at a discount.'},
            'subdomain_label': ''}


def test_batches_forms_one_batch_per_page_with_input_file(root):
    config = setup_root(root)
    out = form(root, config)
    entries = manifest(root)
    assert len(entries) == 1 and entries[0]['items'] == ['whizlabs/01']
    assert 'exam-bank-reader' in out and 'llm-scrape-0001' in out and 'whizlabs 01: ok' in out
    data = store.read_json(root / 'exam-bank/pmle/batches/llm-scrape/llm-scrape-0001.in.json')
    assert data['source'] == 'whizlabs' and data['url'] == url_of(config)
    assert data['txt_path'].endswith('raw/whizlabs/01.txt')
    form(root, config)                               # same page again, no second Batch
    assert len(manifest(root)) == 1


def test_apply_writes_source_file_and_a_changed_page_replaces_its_records(root):
    config = setup_root(root)
    form(root, config)
    write_result(root, 'llm-scrape-0001', [
        question(explanations={'A': 'Dataflow is the managed runner for Apache Beam.'}),
        second_question(), {'n': 3, 'status': 'skipped', 'reason': 'Needs an image.'}])
    out = apply(root)
    path = root / 'exam-bank/pmle/sources/whizlabs.jsonl'
    rows = store.read_jsonl(path)
    assert [r['sources'][0]['source_question_no'] for r in rows] == ['1', '2']
    assert rows[0]['choices'][0]['explanation'].startswith('Dataflow is')
    assert rows[0]['answer'] == ['A'] and rows[1]['answer'] == []
    assert rows[1]['sources'][0]['explanation_block'].startswith('Spot VMs')
    assert rows[1]['sources'][0]['scraped_at'] == NOW and rows[1]['lineage'] == 'scraped'
    assert meta(root)['status'] == 'ok' and meta(root)['applied'] == 'llm-scrape-0001'
    assert '[]' in out
    # The page changes: its records are replaced, another page's stay.
    other = store.dump_jsonl([{'sources': [{'url': 'https://other/', 'name': 'whizlabs'}]}])
    path.write_bytes(other + path.read_bytes())
    form(root, config, html=CHANGED, now='2026-12-01T00:00:00Z')
    write_result(root, 'llm-scrape-0002', [second_question()])
    apply(root)
    rows = store.read_jsonl(path)
    assert [r['sources'][0]['source_question_no'] for r in rows[1:]] == ['2']
    assert rows[0]['sources'][0]['url'] == 'https://other/'


def test_zero_ok_questions_fails_the_page_and_state_lists_it(root):
    config = setup_root(root)
    form(root, config)
    write_result(root, 'llm-scrape-0001', [{'n': 1, 'status': 'skipped', 'reason': 'Needs an image.'}])
    apply(root)
    assert meta(root)['status'] == 'failed: no questions'
    assert 'failed: no questions' in run_eb('state', 'pmle', cwd=root).stdout


def test_rejected_questions_requeue_then_drop_after_attempt_three(root):
    config = setup_root(root)
    form(root, config)
    bad = question(n=9, question='A reworded stem that is not on the page?')
    write_result(root, 'llm-scrape-0001', [question(), bad])
    out = apply(root)
    entries = manifest(root)
    assert len(entries) == 2 and entries[1]['retry_of'] == 'llm-scrape-0001' and entries[1]['attempt'] == 2
    assert 'llm-scrape-0002' in out
    retry_input = root / 'exam-bank/pmle/batches/llm-scrape/llm-scrape-0002.in.json'
    assert store.read_json(retry_input)['only'] == [9]
    assert 'applied' not in meta(root)
    for batch in ('llm-scrape-0002', 'llm-scrape-0003'):
        write_result(root, batch, [bad])
        apply(root)
    assert len(manifest(root)) == 3
    rows = store.read_jsonl(root / 'exam-bank/pmle/sources/whizlabs.jsonl')
    assert [r['sources'][0]['source_question_no'] for r in rows] == ['1']
    assert meta(root)['status'] == 'done-partial'
    log = store.read_jsonl(root / 'exam-bank/pmle/log.jsonl')
    assert [(e['source'], e['ref']) for e in log if e['kind'] == 'dropped'] == [('whizlabs', '9')]
    assert 'dropped: whizlabs 9' in run_eb('state', 'pmle', cwd=root).stdout


def test_missing_results_requeue_the_page_and_attempt_three_is_failed_not_done(root):
    config = setup_root(root)
    form(root, config)
    out = ''
    for _ in range(3):
        out = apply(root)              # the wave ran, the worker wrote nothing
    assert len(manifest(root)) == 3
    assert 'failed 1' in out and 'applied' not in meta(root)


def test_merge_marks_an_answer_only_an_untrusted_source_gives_uncertain(root):
    config = setup_root(root)
    form(root, config)
    write_result(root, 'llm-scrape-0001', [question()])
    apply(root)
    result = run_eb('merge', 'pmle', cwd=root)
    assert result.returncode == 0, result.stderr
    rows = store.read_jsonl(root / 'exam-bank/pmle/bank.jsonl')
    assert len(rows) == 1 and rows[0]['answer'] == ['A'] and rows[0]['uncertain'] is True
