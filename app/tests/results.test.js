// Results screen (spec 0002, Results screen): getResults, rebuilt from rows.
const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, settingsValues } = require('./bank-fixture.js');

const STATE_HEADERS = ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'];
const ATTEMPT_HEADERS = ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'];
const TEST_HEADERS = ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'];
const ITEM_HEADERS = ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'];
const REPORT_HEADERS = ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution'];
const NOW = '2026-11-18T09:00:00Z';
const TEST_ID = 't_20261118T081500Z';

function sheet({ bank = fixtureBank(), settings = {}, states = [], attempts = [], tests = [], items = [] } = {}) {
  const fake = makeFakeAdapter({ now: NOW });
  fake.props.setup_done_at = '2026-11-01T00:00:00Z';
  fake.addTab('Questions', bank);
  fake.addTab('Settings', settingsValues(settings), { plainText: true, frozenRows: 1 });
  fake.addTab('QuestionState', [STATE_HEADERS, ...states], { plainText: true, frozenRows: 1 });
  fake.addTab('Attempts', [ATTEMPT_HEADERS, ...attempts], { plainText: true, frozenRows: 1 });
  fake.addTab('MockTests', [TEST_HEADERS, ...tests], { plainText: true, frozenRows: 1 });
  fake.addTab('MockTestItems', [ITEM_HEADERS, ...items], { plainText: true, frozenRows: 1 });
  fake.addTab('Reports', [REPORT_HEADERS], { plainText: true, frozenRows: 1 });
  return { fake, server: makeServer(fake.adapter) };
}

function rowsOf(fake, name) {
  const [headers, ...rows] = fake.values(name);
  return rows.map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i]])));
}

function row(headers, o) {
  return headers.map((h) => (o[h] === undefined ? '' : o[h]));
}

function itemRow(position, id, selected = '', flagged = 'FALSE', extra = {}) {
  return row(ITEM_HEADERS, { test_id: TEST_ID, position: String(position), question_id: id, choice_order: 'ABCD', selected, flagged, question_updated_at: '2026-11-01T10:00:00Z', ...extra });
}

function testRow(extra = {}) {
  return row(TEST_HEADERS, { test_id: TEST_ID, status: 'in_progress', started_at: '2026-11-18T08:15:00Z', question_count: '5', minutes_allowed: '60', seconds_left: '1200', ...extra });
}

function stateRow(o) {
  return row(STATE_HEADERS, { bookmarked: 'FALSE', attempts: '1', correct_count: '1', last_result: 'correct', ...o });
}

// Five items stored out of order. Answers: q_0428 B, q_dba0 A,C (multi),
// q_dfd5 A, q_8c09 B, q_c1db A.
function fiveItems() {
  return [
    itemRow(3, 'q_dfd5922f5aa9', 'C'), // wrong
    itemRow(1, 'q_042896dc1966', 'B', 'TRUE'), // correct, Flagged
    itemRow(5, 'q_c1db13ab836d', '', 'TRUE'), // skipped, Flagged
    itemRow(2, 'q_dba0082ec68e', 'A'), // part answered: wrong
    itemRow(4, 'q_8c09b37123eb', 'B'), // correct
  ];
}

function submitted() {
  const run = sheet({ tests: [testRow()], items: fiveItems() });
  run.server.submitMockTest([], 1100, false);
  return run;
}

// A second sheet holding the first one's rows, with the bank edited by `edit`.
function reopened(first, edit) {
  const bank = fixtureBank();
  edit(bank);
  const [, ...attempts] = first.fake.values('Attempts');
  const [, ...tests] = first.fake.values('MockTests');
  return sheet({ bank, attempts, tests });
}

function dropQuestion(bank, id) {
  bank.splice(bank.findIndex((r) => r[0] === id), 1);
}

test('a test is rebuilt from its MockTests and Attempts rows, in test order', () => {
  const first = submitted();
  const { server } = reopened(first, () => {});
  const res = server.getResults(TEST_ID);
  assert.equal(res.error, undefined);
  assert.equal(res.test.test_id, TEST_ID);
  assert.equal(res.test.question_count, 5);
  assert.equal(res.test.correct_count, 2);
  assert.equal(res.test.score_pct, '40.0');
  assert.equal(res.test.skipped, 1);
  assert.equal(res.test.seconds_left, 1100);
  assert.deepEqual(res.attempts.map((a) => [a.position, a.question_id, a.selected, a.correct_answer, a.result, a.flagged, a.bank, a.edited]), [
    [1, 'q_042896dc1966', 'B', 'B', 'correct', true, 'ok', false],
    [2, 'q_dba0082ec68e', 'A', 'A,C', 'wrong', false, 'ok', false],
    [3, 'q_dfd5922f5aa9', 'C', 'A', 'wrong', false, 'ok', false],
    [4, 'q_8c09b37123eb', 'B', 'B', 'correct', false, 'ok', false],
    [5, 'q_c1db13ab836d', '', 'A', 'skipped', true, 'ok', false],
  ]);
});

test('the breakdown groups by the current Section and Subdomain and its Total equals the stored score', () => {
  const { server } = reopened(submitted(), () => {});
  const { breakdown, test: header } = server.getResults(TEST_ID);
  assert.deepEqual(breakdown.sections, [
    {
      section: '1', label: 'Section 1', correct: 2, count: 4, pct: '50.0',
      subdomains: [
        { subdomain: '1.1', title: 'Framing ML problems', correct: 1, count: 2, pct: '50.0' },
        { subdomain: '1.2', title: 'Data and feature design', correct: 1, count: 2, pct: '50.0' },
      ],
    },
    {
      section: '2', label: 'Section 2', correct: 0, count: 1, pct: '0.0',
      subdomains: [{ subdomain: '2.1', title: 'Architecting low-code solutions', correct: 0, count: 1, pct: '0.0' }],
    },
  ]);
  assert.equal(breakdown.notInBank, null);
  assert.deepEqual(breakdown.total, { correct: header.correct_count, count: header.question_count, pct: header.score_pct });
});

test('a question gone from the bank gets a Not in bank row and the score does not move', () => {
  const { server } = reopened(submitted(), (bank) => dropQuestion(bank, 'q_8c09b37123eb'));
  const res = server.getResults(TEST_ID);
  assert.deepEqual(res.breakdown.notInBank, { correct: 1, count: 1, pct: '100.0' });
  assert.deepEqual(res.breakdown.total, { correct: 2, count: 5, pct: '40.0' });
  assert.equal(res.test.score_pct, '40.0');
  const sectionSum = res.breakdown.sections.reduce((n, s) => n + s.count, 0) + res.breakdown.notInBank.count;
  assert.equal(sectionSum, 5);
  const gone = res.attempts[3];
  assert.deepEqual([gone.question_id, gone.bank, gone.result], ['q_8c09b37123eb', 'missing', 'correct']);
  assert.equal(res.attempts.length, 5);
});

test('an edited question is marked edited and keeps its stored result; a retired one is marked retired', () => {
  const { server } = reopened(submitted(), (bank) => {
    const col = bank[0].indexOf('updated_at');
    bank.find((r) => r[0] === 'q_dba0082ec68e')[col] = '2026-11-10T10:00:00Z';
    bank.find((r) => r[0] === 'q_dfd5922f5aa9')[bank[0].indexOf('status')] = 'retired';
  });
  const res = server.getResults(TEST_ID);
  const [edited, retired] = [res.attempts[1], res.attempts[2]];
  assert.deepEqual([edited.edited, edited.bank, edited.result, edited.question_updated_at], [true, 'ok', 'wrong', '2026-11-01T10:00:00Z']);
  assert.deepEqual([retired.bank, retired.edited], ['retired', false]);
  assert.equal(res.breakdown.total.correct, 2);
});

test('getResults writes nothing', () => {
  const first = submitted();
  const run = reopened(first, () => {});
  const before = ['Attempts', 'QuestionState', 'MockTests', 'MockTestItems', 'Reports'].map((n) => run.fake.values(n));
  run.server.getResults(TEST_ID);
  assert.deepEqual(['Attempts', 'QuestionState', 'MockTests', 'MockTestItems', 'Reports'].map((n) => run.fake.values(n)), before);
});

test('an unknown or unfinished test has no results', () => {
  const { server } = sheet({ tests: [testRow()], items: fiveItems() });
  assert.equal(server.getResults(TEST_ID).error, 'no_test');
  assert.equal(server.getResults('t_nope').error, 'no_test');
});
