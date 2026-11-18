// History screen (spec 0002, History screen): getHistory.
const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, settingsValues } = require('./bank-fixture.js');

const TEST_HEADERS = ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'];

function sheet(tests) {
  const fake = makeFakeAdapter({ now: '2026-11-18T09:00:00Z' });
  fake.props.setup_done_at = '2026-11-01T00:00:00Z';
  fake.addTab('Questions', fixtureBank());
  fake.addTab('Settings', settingsValues(), { plainText: true, frozenRows: 1 });
  fake.addTab('MockTests', [TEST_HEADERS, ...tests.map((t) => TEST_HEADERS.map((h) => (t[h] === undefined ? '' : t[h])))], { plainText: true, frozenRows: 1 });
  return makeServer(fake.adapter);
}

function row(id, status, extra = {}) {
  return { test_id: id, status, started_at: '2026-11-10T08:00:00Z', question_count: '10', minutes_allowed: '60', seconds_left: '600', ...extra };
}

function submitted(id, at, extra = {}) {
  return row(id, 'submitted', { submitted_at: at, correct_count: '7', score_pct: '70.0', ...extra });
}

test('getHistory returns only submitted tests, newest first', () => {
  const server = sheet([
    submitted('t_a', '2026-11-10T09:00:00Z'),
    row('t_b', 'discarded'),
    submitted('t_c', '2026-11-12T09:00:00Z', { correct_count: '9', score_pct: '90.0' }),
    row('t_d', 'in_progress'),
  ]);
  const { tests } = server.getHistory();
  assert.deepEqual(tests.map((t) => t.test_id), ['t_c', 't_a']);
  assert.equal(tests[0].score_pct, '90.0');
  assert.equal(tests[0].correct_count, 9);
  assert.equal(tests[0].question_count, 10);
  assert.equal(tests[0].submitted_on, '2026-11-12');
  assert.equal(tests[0].seconds_left, 600);
  assert.equal(tests[0].minutes_allowed, 60);
});

test('getHistory with no submitted test is an empty list', () => {
  assert.deepEqual(sheet([row('t_b', 'discarded'), row('t_d', 'in_progress')]).getHistory(), { tests: [] });
});

test('getHistory marks a timed-out test by seconds_left 0 and leaves no extra fields', () => {
  const { tests } = sheet([submitted('t_a', '2026-11-10T09:00:00Z', { seconds_left: '0' })]).getHistory();
  assert.equal(tests[0].seconds_left, 0);
  assert.equal('index' in tests[0], false);
  assert.equal('skipped' in tests[0], false);
});

test('getHistory puts the later row first when two tests share a submit time', () => {
  const { tests } = sheet([submitted('t_a', '2026-11-10T09:00:00Z'), submitted('t_b', '2026-11-10T09:00:00Z')]).getHistory();
  assert.deepEqual(tests.map((t) => t.test_id), ['t_b', 't_a']);
});
