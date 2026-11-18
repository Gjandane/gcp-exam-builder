// Mock Test submit (spec 0002, Submit): submitMockTest and load step 6.
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

function running(opts = {}) {
  return sheet({ tests: [testRow()], items: fiveItems(), ...opts });
}

// ---- Step 1: Attempts

test('submit appends one mock Attempts row per item in position order, with every column and flagged copied', () => {
  const { fake, server } = running();
  const res = server.submitMockTest([], 1100, false);
  assert.equal(res.error, undefined);
  assert.equal(res.test_id, TEST_ID);
  const base = { answered_at: NOW, mode: 'mock', test_id: TEST_ID, question_updated_at: '2026-11-01T10:00:00Z' };
  assert.deepEqual(rowsOf(fake, 'Attempts'), [
    { ...base, question_id: 'q_042896dc1966', selected: 'B', correct_answer: 'B', result: 'correct', flagged: 'TRUE' },
    { ...base, question_id: 'q_dba0082ec68e', selected: 'A', correct_answer: 'A,C', result: 'wrong', flagged: 'FALSE' },
    { ...base, question_id: 'q_dfd5922f5aa9', selected: 'C', correct_answer: 'A', result: 'wrong', flagged: 'FALSE' },
    { ...base, question_id: 'q_8c09b37123eb', selected: 'B', correct_answer: 'B', result: 'correct', flagged: 'FALSE' },
    { ...base, question_id: 'q_c1db13ab836d', selected: '', correct_answer: 'A', result: 'skipped', flagged: 'TRUE' },
  ]);
});

test('the picks sent with the submit are written first and graded', () => {
  const { fake, server } = running();
  // Position 5 gets its answer, position 3 its correct pick, position 1 loses its Flag.
  server.submitMockTest([
    { position: 5, selected: ['A'], flagged: true },
    { position: 3, selected: ['A'], flagged: false },
    { position: 1, selected: ['B'], flagged: false },
  ], 900, false);
  const byId = Object.fromEntries(rowsOf(fake, 'Attempts').map((r) => [r.question_id, r]));
  assert.equal(byId.q_c1db13ab836d.result, 'correct');
  assert.equal(byId.q_c1db13ab836d.flagged, 'TRUE');
  assert.equal(byId.q_dfd5922f5aa9.result, 'correct');
  assert.equal(byId.q_042896dc1966.flagged, 'FALSE');
  assert.equal(rowsOf(fake, 'MockTests')[0].seconds_left, '900');
});

test('a multi-select needs the exact set: part answered and a wrong pair are wrong, the full set is correct', () => {
  const items = [
    itemRow(1, 'q_dba0082ec68e', 'A'),
    itemRow(2, 'q_01dc6054f16a', 'A,B,C', 'FALSE', { choice_order: 'ABCDE' }),
    itemRow(3, 'q_4dc776a81b9a', 'A,C'),
  ];
  const { fake, server } = sheet({ tests: [testRow({ question_count: '3' })], items });
  server.submitMockTest([], 100, false);
  assert.deepEqual(rowsOf(fake, 'Attempts').map((r) => [r.selected, r.result]), [['A', 'wrong'], ['A,B,C', 'correct'], ['A,C', 'wrong']]);
});

// ---- Step 2: QuestionState

test('submit moves each graded question through the Leitner table and leaves a skipped one untouched', () => {
  const states = [
    // q_0428: due yesterday in box 2, correct -> box 3, due today + 4.
    stateRow({ question_id: 'q_042896dc1966', box: '2', due_at: '2026-11-17', last_seen_at: '2026-11-15T08:00:00Z' }),
    // q_8c09: not due, correct -> box held, counters up.
    stateRow({ question_id: 'q_8c09b37123eb', box: '3', due_at: '2026-11-25', last_seen_at: '2026-11-14T08:00:00Z' }),
    // q_c1db: skipped, row exactly as it was.
    stateRow({ question_id: 'q_c1db13ab836d', box: '4', due_at: '2026-11-19', last_seen_at: '2026-11-10T08:00:00Z', note: 'keep' }),
  ];
  const { fake, server } = running({ states });
  const res = server.submitMockTest([], 1000, false);
  const byId = Object.fromEntries(rowsOf(fake, 'QuestionState').map((r) => [r.question_id, r]));
  assert.deepEqual(byId.q_042896dc1966, {
    question_id: 'q_042896dc1966', box: '3', due_at: '2026-11-22', attempts: '2', correct_count: '2',
    last_seen_at: NOW, last_result: 'correct', bookmarked: 'FALSE', note: '', note_updated_at: '',
  });
  assert.equal(byId.q_8c09b37123eb.box, '3');
  assert.equal(byId.q_8c09b37123eb.due_at, '2026-11-25');
  assert.equal(byId.q_8c09b37123eb.attempts, '2');
  assert.equal(byId.q_8c09b37123eb.last_seen_at, NOW);
  assert.deepEqual(byId.q_c1db13ab836d, {
    question_id: 'q_c1db13ab836d', box: '4', due_at: '2026-11-19', attempts: '1', correct_count: '1',
    last_seen_at: '2026-11-10T08:00:00Z', last_result: 'correct', bookmarked: 'FALSE', note: 'keep', note_updated_at: '',
  });
  // Wrong on unseen questions (part answered included): new rows in box 1, due tomorrow.
  for (const id of ['q_dba0082ec68e', 'q_dfd5922f5aa9']) {
    assert.deepEqual(byId[id], {
      question_id: id, box: '1', due_at: '2026-11-19', attempts: '1', correct_count: '0',
      last_seen_at: NOW, last_result: 'wrong', bookmarked: 'FALSE', note: '', note_updated_at: '',
    });
  }
  assert.equal(Object.keys(byId).length, 5);
  // The reply carries the moved rows only, with the effective box and due date.
  assert.deepEqual(Object.keys(res.states).sort(), ['q_042896dc1966', 'q_8c09b37123eb', 'q_dba0082ec68e', 'q_dfd5922f5aa9']);
  assert.equal(res.states.q_042896dc1966.effective_box, 3);
  assert.equal(res.states.q_042896dc1966.effective_due_at, '2026-11-22');
});

test('a skipped item on an unseen question creates no QuestionState row', () => {
  const { fake, server } = sheet({ tests: [testRow({ question_count: '1' })], items: [itemRow(1, 'q_c1db13ab836d')] });
  server.submitMockTest([], 100, false);
  assert.equal(rowsOf(fake, 'Attempts')[0].result, 'skipped');
  assert.deepEqual(rowsOf(fake, 'QuestionState'), []);
});

test('a changed answer makes the question due in box 1 at submit, so a correct pick gives box 2', () => {
  // The last graded answer was C; the bank now says B.
  const attempts = [row(ATTEMPT_HEADERS, { answered_at: '2026-11-15T08:00:00Z', question_id: 'q_042896dc1966', mode: 'review', selected: 'C', correct_answer: 'C', result: 'correct', question_updated_at: '2026-10-01T10:00:00Z' })];
  const states = [stateRow({ question_id: 'q_042896dc1966', box: '4', due_at: '2026-11-30', last_seen_at: '2026-11-15T08:00:00Z' })];
  const { fake, server } = sheet({ tests: [testRow({ question_count: '1' })], items: [itemRow(1, 'q_042896dc1966', 'B')], states, attempts });
  server.submitMockTest([], 100, false);
  const state = rowsOf(fake, 'QuestionState')[0];
  assert.equal(state.box, '2');
  assert.equal(state.due_at, '2026-11-20');
});

// ---- Steps 3 and 4: MockTests and MockTestItems

test('submit sets the MockTests row and clears MockTestItems', () => {
  const other = row(TEST_HEADERS, { test_id: 't_20261110T081500Z', status: 'submitted', started_at: '2026-11-10T08:15:00Z', submitted_at: '2026-11-10T09:00:00Z', question_count: '3', minutes_allowed: '60', seconds_left: '100', correct_count: '2', score_pct: '66.7' });
  const { fake, server } = running({ tests: [other, testRow()] });
  const res = server.submitMockTest([], 1100.7, false);
  const tests = rowsOf(fake, 'MockTests');
  assert.deepEqual(fake.values('MockTests')[1], other);
  assert.deepEqual(tests[1], {
    test_id: TEST_ID, status: 'submitted', started_at: '2026-11-18T08:15:00Z', submitted_at: NOW,
    question_count: '5', minutes_allowed: '60', seconds_left: '1100', correct_count: '2', score_pct: '40.0',
  });
  assert.deepEqual(fake.values('MockTestItems'), [ITEM_HEADERS]);
  assert.deepEqual(res.test, {
    test_id: TEST_ID, submitted_at: NOW, submitted_on: '2026-11-18', question_count: 5, minutes_allowed: 60,
    seconds_left: 1100, correct_count: 2, score_pct: '40.0', skipped: 1,
  });
});

test('score_pct is correct over question_count to one decimal, skipped counted as wrong', () => {
  const items = [itemRow(1, 'q_042896dc1966', 'B'), itemRow(2, 'q_dfd5922f5aa9', 'A'), itemRow(3, 'q_c1db13ab836d')];
  const { fake, server } = sheet({ tests: [testRow({ question_count: '3' })], items });
  server.submitMockTest([], 100, false);
  const t = rowsOf(fake, 'MockTests')[0];
  assert.equal(t.correct_count, '2');
  assert.equal(t.score_pct, '66.7');
});

test('a timed-out submit stores seconds_left 0', () => {
  const { fake, server } = running();
  const res = server.submitMockTest([], 3, true);
  assert.equal(rowsOf(fake, 'MockTests')[0].seconds_left, '0');
  assert.equal(res.test.seconds_left, 0);
});

test('the submit reply carries the four Review mode counts after the move', () => {
  const { server } = running();
  const res = server.submitMockTest([], 100, false);
  // The two wrong answers put two questions on the Wrong list.
  assert.equal(res.counts.wrong, 2);
  assert.equal(res.counts.all, 11);
  assert.deepEqual(res.counts, server.getReviewList('all').counts);
});

// ---- Refusals

test('a second submit, and a save after submit, return not_unfinished and write nothing', () => {
  const { fake, server } = running();
  server.submitMockTest([], 100, false);
  const tabs = () => ['Attempts', 'QuestionState', 'MockTests'].map((t) => fake.values(t));
  const before = tabs();
  assert.equal(server.submitMockTest([], 50, false).error, 'not_unfinished');
  assert.equal(server.saveMockTest([{ position: 1, selected: ['A'], flagged: false }], 50).error, 'not_unfinished');
  assert.deepEqual(tabs(), before);
});

test('submit with a bad change, or with the lock held, writes nothing', () => {
  const { fake, server } = running();
  const tabs = () => ['Attempts', 'QuestionState', 'MockTests', 'MockTestItems'].map((t) => fake.values(t));
  const before = tabs();
  assert.equal(server.submitMockTest([{ position: 9, selected: ['A'], flagged: false }], 100, false).error, 'bad_changes');
  assert.deepEqual(tabs(), before);
  fake.holdLockElsewhere();
  assert.equal(server.submitMockTest([], 100, false).error, 'busy');
  assert.deepEqual(tabs(), before);
});

// ---- Recovery: load step 6

const TABS = ['Attempts', 'QuestionState', 'MockTests', 'MockTestItems'];

// A submit cut off after step 1: a real submit runs on one sheet, and its
// Attempts rows go back on the sheet as it stood before the submit.
function cutAfterStep1(opts = {}) {
  const live = running(opts);
  live.server.submitMockTest([], 1100, false);
  const appended = live.fake.values('Attempts').slice(1 + (opts.attempts || []).length);
  const cut = running({ ...opts, tests: [testRow({ seconds_left: '1100' })], attempts: [...(opts.attempts || []), ...appended] });
  return { live, cut };
}

test('load finishes a submit cut off after step 1, appends nothing, and matches the live submit', () => {
  const states = [stateRow({ question_id: 'q_042896dc1966', box: '2', due_at: '2026-11-17', last_seen_at: '2026-11-15T08:00:00Z' })];
  const { live, cut } = cutAfterStep1({ states });
  assert.equal(cut.fake.values('Attempts').length, 6);
  // The load runs days later: the grading date still comes from answered_at.
  cut.fake.setNow('2026-11-20T10:00:00Z');
  const home = cut.server.load();
  assert.equal(home.screen, 'home');
  assert.equal(home.mockTest, null);
  for (const t of TABS) assert.deepEqual(cut.fake.values(t), live.fake.values(t), t);
});

test('running the recovery twice changes nothing', () => {
  const { cut } = cutAfterStep1();
  cut.server.load();
  const once = TABS.map((t) => cut.fake.values(t));
  cut.server.load();
  assert.deepEqual(TABS.map((t) => cut.fake.values(t)), once);
});

test('a submit cut off after step 2 does not move a question twice', () => {
  const { live, cut } = cutAfterStep1();
  // Step 2 already ran: QuestionState as the live submit left it.
  const s = running({ tests: [testRow({ seconds_left: '1100' })], attempts: cut.fake.values('Attempts').slice(1), states: live.fake.values('QuestionState').slice(1) });
  s.server.load();
  for (const t of TABS) assert.deepEqual(s.fake.values(t), live.fake.values(t), t);
});

test('a submit call on a test whose step 1 already ran finishes it without appending', () => {
  const { live, cut } = cutAfterStep1();
  const res = cut.server.submitMockTest([{ position: 5, selected: ['A'], flagged: false }], 10, false);
  assert.equal(res.test.correct_count, 2);
  for (const t of TABS) assert.deepEqual(cut.fake.values(t), live.fake.values(t), t);
});

test('load with the lock held during a recovery returns busy and writes nothing', () => {
  const { cut } = cutAfterStep1();
  const before = TABS.map((t) => cut.fake.values(t));
  cut.fake.holdLockElsewhere();
  assert.equal(cut.server.load().error, 'busy');
  assert.deepEqual(TABS.map((t) => cut.fake.values(t)), before);
});
