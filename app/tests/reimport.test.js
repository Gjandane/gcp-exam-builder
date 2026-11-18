// Re-import during a Mock Test (spec 0002, Re-import during a test): the
// reconcile in getMockTest and submitMockTest.
const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, settingsValues, setCell } = require('./bank-fixture.js');

const STATE_HEADERS = ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'];
const ATTEMPT_HEADERS = ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'];
const TEST_HEADERS = ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'];
const ITEM_HEADERS = ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'];
const REPORT_HEADERS = ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution'];
const NOW = '2026-11-18T09:00:00Z';
const TEST_ID = 't_20261118T081500Z';
const OLD_STAMP = '2026-11-01T10:00:00Z';
const NEW_STAMP = '2026-11-17T12:00:00Z';
const TABS = ['Attempts', 'QuestionState', 'MockTests', 'MockTestItems'];

// Fixture sheet rows: 2 q_0428 B, 3 q_dba0 A,C, 4 q_dfd5 A, 5 q_8c09 B, 6 q_c1db A.
const ROW = { q_042896dc1966: 2, q_dba0082ec68e: 3, q_dfd5922f5aa9: 4, q_8c09b37123eb: 5, q_c1db13ab836d: 6 };

function sheet({ bank = fixtureBank(), tests = [], items = [], states = [] } = {}) {
  const fake = makeFakeAdapter({ now: NOW });
  fake.props.setup_done_at = '2026-11-01T00:00:00Z';
  fake.addTab('Questions', bank);
  fake.addTab('Settings', settingsValues(), { plainText: true, frozenRows: 1 });
  fake.addTab('QuestionState', [STATE_HEADERS, ...states], { plainText: true, frozenRows: 1 });
  fake.addTab('Attempts', [ATTEMPT_HEADERS], { plainText: true, frozenRows: 1 });
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
  return row(ITEM_HEADERS, { test_id: TEST_ID, position: String(position), question_id: id, choice_order: 'ABCD', selected, flagged, question_updated_at: OLD_STAMP, ...extra });
}

function testRow(extra = {}) {
  return row(TEST_HEADERS, { test_id: TEST_ID, status: 'in_progress', started_at: '2026-11-18T08:15:00Z', question_count: '5', minutes_allowed: '60', seconds_left: '1200', ...extra });
}

// Five items, all answered correctly except position 4; position 2 Flagged.
function fiveItems() {
  return [
    itemRow(1, 'q_042896dc1966', 'B'),
    itemRow(2, 'q_dba0082ec68e', 'A,C', 'TRUE'),
    itemRow(3, 'q_dfd5922f5aa9', 'A'),
    itemRow(4, 'q_8c09b37123eb', 'C'),
    itemRow(5, 'q_c1db13ab836d', 'A'),
  ];
}

// The bank after a re-import: each id in `retire` is retired, each in `edit`
// has a new updated_at, each in `remove` is gone.
function reimported({ retire = [], edit = [], remove = [] } = {}) {
  const bank = fixtureBank();
  retire.forEach((id) => setCell(bank, ROW[id], 'status', 'retired'));
  edit.forEach((id) => setCell(bank, ROW[id], 'updated_at', NEW_STAMP));
  const gone = remove.map((id) => ROW[id]).sort((a, b) => b - a);
  gone.forEach((n) => bank.splice(n - 1, 1));
  return bank;
}

function running(bankOpts, extra = {}) {
  return sheet({ bank: reimported(bankOpts), tests: [testRow()], items: fiveItems(), ...extra });
}

// ---- getMockTest: the reconcile on load

test('a bank that did not change leaves the test and the sheet as they were', () => {
  const { fake, server } = sheet({ tests: [testRow()], items: fiveItems() });
  const before = TABS.map((t) => fake.values(t));
  const res = server.getMockTest();
  assert.deepEqual(res.notices, []);
  assert.deepEqual(res.resetRows, []);
  assert.equal(res.test.question_count, 5);
  assert.deepEqual(TABS.map((t) => fake.values(t)), before);
});

test('a missing and a retired item are dropped, the count goes down and positions close up', () => {
  const { fake, server } = running({ remove: ['q_dba0082ec68e'], retire: ['q_042896dc1966'] });
  const res = server.getMockTest();
  assert.equal(res.test.question_count, 3);
  assert.deepEqual(res.test.items.map((i) => [i.position, i.question_id]), [[1, 'q_dfd5922f5aa9'], [2, 'q_8c09b37123eb'], [3, 'q_c1db13ab836d']]);
  assert.equal(rowsOf(fake, 'MockTests')[0].question_count, '3');
  assert.equal(rowsOf(fake, 'MockTests')[0].status, 'in_progress');
  assert.deepEqual(rowsOf(fake, 'MockTestItems').map((i) => [i.position, i.question_id]), [['1', 'q_dfd5922f5aa9'], ['2', 'q_8c09b37123eb'], ['3', 'q_c1db13ab836d']]);
  assert.deepEqual(res.notices, [{ text: 'The bank changed during this test. 2 questions were removed, the test now has 3.', links: [] }]);
  assert.deepEqual(res.resetRows, []);
  assert.equal(res.test.answered, 3);
});

test('a dropped item writes no Attempts row and moves no QuestionState', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'] });
  server.getMockTest();
  assert.deepEqual(fake.values('Attempts').length, 1);
  assert.deepEqual(fake.values('QuestionState').length, 1);
});

test('an edited item keeps its place and Flag, loses its answer, gets a new choice_order and updated_at', () => {
  const items = fiveItems();
  items[1] = itemRow(2, 'q_dba0082ec68e', 'A,C', 'TRUE', { choice_order: 'DCBA' });
  const { fake, server } = running({ edit: ['q_dba0082ec68e'] }, { items });
  const res = server.getMockTest();
  const stored = rowsOf(fake, 'MockTestItems')[1];
  assert.equal(stored.position, '2');
  assert.equal(stored.question_id, 'q_dba0082ec68e');
  assert.equal(stored.flagged, 'TRUE');
  assert.equal(stored.selected, '');
  assert.equal(stored.question_updated_at, NEW_STAMP);
  assert.notEqual(stored.choice_order, 'DCBA');
  assert.deepEqual(stored.choice_order.split('').sort(), ['A', 'B', 'C', 'D']);
  assert.deepEqual(res.test.items[1], { position: 2, question_id: 'q_dba0082ec68e', choice_order: stored.choice_order, selected: '', flagged: true, question_updated_at: NEW_STAMP });
  assert.equal(res.test.question_count, 5);
  assert.equal(res.test.answered, 4);
  assert.equal(res.test.flagged, 1);
  // The other items are untouched.
  assert.equal(rowsOf(fake, 'MockTestItems')[0].selected, 'B');
});

test('the notice gives the counts and one link per reset question, and the reply carries their current bank rows', () => {
  const { server } = running({ retire: ['q_042896dc1966'], edit: ['q_dba0082ec68e', 'q_c1db13ab836d'] });
  const res = server.getMockTest();
  assert.deepEqual(res.notices, [{
    text: 'The bank changed during this test. 1 question was removed, the test now has 4. 2 questions were edited and their answers were cleared:',
    links: [1, 4], // positions after the close-up
  }]);
  assert.deepEqual(res.resetRows.map((r) => [r.id, r.updated_at]), [['q_dba0082ec68e', NEW_STAMP], ['q_c1db13ab836d', NEW_STAMP]]);
  assert.equal(Object.keys(res.resetRows[0]).length, 30);
});

test('an edit alone has no removed clause and a single edit reads in the singular', () => {
  const { server } = running({ edit: ['q_8c09b37123eb'] });
  const res = server.getMockTest();
  assert.deepEqual(res.notices, [{ text: 'The bank changed during this test. 1 question was edited and its answer was cleared:', links: [4] }]);
});

test('an item dropped and edited at once is dropped', () => {
  const { server } = running({ retire: ['q_dfd5922f5aa9'], edit: ['q_dfd5922f5aa9'] });
  const res = server.getMockTest();
  assert.equal(res.test.question_count, 4);
  assert.deepEqual(res.notices[0].links, []);
});

test('the reconcile runs once: a second read finds nothing to do and changes nothing', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'], edit: ['q_dba0082ec68e'] });
  server.getMockTest();
  const after = TABS.map((t) => fake.values(t));
  const again = server.getMockTest();
  assert.deepEqual(again.notices, []);
  assert.deepEqual(again.resetRows, []);
  assert.deepEqual(TABS.map((t) => fake.values(t)), after);
});

test('when every item is dropped the test is discarded, the items cleared and no Attempts written', () => {
  const all = Object.keys(ROW);
  const { fake, server } = running({ retire: all.slice(0, 3), remove: all.slice(3) });
  const res = server.getMockTest();
  assert.equal(res.test, null);
  assert.equal(res.discarded, true);
  assert.equal(res.notices.length, 1);
  assert.match(res.notices[0], /none of its questions are left/);
  assert.equal(rowsOf(fake, 'MockTests')[0].status, 'discarded');
  assert.deepEqual(fake.values('MockTestItems'), [ITEM_HEADERS]);
  assert.equal(fake.values('Attempts').length, 1);
  // Home no longer offers the test, and the next read finds none.
  assert.equal(server.load().mockTest, null);
  assert.deepEqual(server.getMockTest(), { test: null });
});

test('getMockTest with the lock held elsewhere returns busy and writes nothing', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'] });
  const before = TABS.map((t) => fake.values(t));
  fake.holdLockElsewhere();
  assert.equal(server.getMockTest().error, 'busy');
  assert.deepEqual(TABS.map((t) => fake.values(t)), before);
});

// ---- Submit, manual: the reconcile runs after the sent changes, before step 1

test('a manual submit that drops an item submits nothing and returns the test for the pause screen', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'] });
  const before = ['Attempts', 'QuestionState'].map((t) => fake.values(t));
  const res = server.submitMockTest([], 1100, false);
  assert.equal(res.test_id, undefined);
  assert.equal(res.unfinished.question_count, 4);
  assert.equal(res.unfinished.seconds_left, 1100);
  assert.deepEqual(res.unfinished.items.map((i) => i.position), [1, 2, 3, 4]);
  assert.deepEqual(res.notices, [{ text: 'The bank changed during this test. 1 question was removed, the test now has 4.', links: [] }]);
  assert.deepEqual(['Attempts', 'QuestionState'].map((t) => fake.values(t)), before);
  const t = rowsOf(fake, 'MockTests')[0];
  assert.equal(t.status, 'in_progress');
  assert.equal(t.question_count, '4');
  assert.equal(t.submitted_at, '');
});

test('a manual submit that resets an item submits nothing and returns the current bank row', () => {
  const { fake, server } = running({ edit: ['q_dfd5922f5aa9'] });
  const res = server.submitMockTest([], 1000, false);
  assert.equal(res.unfinished.items[2].selected, '');
  assert.deepEqual(res.notices[0].links, [3]);
  assert.deepEqual(res.resetRows.map((r) => r.id), ['q_dfd5922f5aa9']);
  assert.equal(fake.values('Attempts').length, 1);
  assert.equal(rowsOf(fake, 'MockTests')[0].status, 'in_progress');
});

test('the sent changes are written first, so a change lands on the position it was made on', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'] });
  // Positions as the page knew them: 3 is q_dfd5, 5 is q_c1db. Flag q_dfd5 and clear q_c1db.
  const res = server.submitMockTest([
    { position: 3, selected: ['A'], flagged: true },
    { position: 5, selected: [], flagged: false },
  ], 900, false);
  assert.ok(res.unfinished);
  const byId = Object.fromEntries(rowsOf(fake, 'MockTestItems').map((i) => [i.question_id, i]));
  assert.equal(byId.q_dfd5922f5aa9.flagged, 'TRUE');
  assert.equal(byId.q_dfd5922f5aa9.position, '2');
  assert.equal(byId.q_c1db13ab836d.selected, '');
  assert.equal(byId.q_c1db13ab836d.position, '4');
});

test('after the notice a second manual submit goes through on the reconciled test', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'], edit: ['q_dfd5922f5aa9'] });
  server.submitMockTest([], 1000, false);
  const res = server.submitMockTest([], 900, false);
  assert.equal(res.test_id, TEST_ID);
  assert.equal(res.notices, undefined);
  assert.equal(res.test.question_count, 4);
  const attempts = rowsOf(fake, 'Attempts');
  assert.deepEqual(attempts.map((a) => [a.question_id, a.result]), [
    ['q_dba0082ec68e', 'correct'], ['q_dfd5922f5aa9', 'skipped'], ['q_8c09b37123eb', 'wrong'], ['q_c1db13ab836d', 'correct'],
  ]);
  assert.equal(attempts[1].question_updated_at, NEW_STAMP);
  const t = rowsOf(fake, 'MockTests')[0];
  assert.equal(t.status, 'submitted');
  assert.equal(t.score_pct, '50.0');
});

test('a manual submit on a bank that did not change goes through at once', () => {
  const { fake, server } = sheet({ tests: [testRow()], items: fiveItems() });
  const res = server.submitMockTest([], 1000, false);
  assert.equal(res.test_id, TEST_ID);
  assert.equal(res.unfinished, undefined);
  assert.equal(fake.values('Attempts').length, 6);
});

test('a manual submit that dropped every item discards the test', () => {
  const all = Object.keys(ROW);
  const { fake, server } = running({ retire: all });
  const res = server.submitMockTest([], 1000, false);
  assert.equal(res.discarded, true);
  assert.match(res.notices[0], /none of its questions are left/);
  assert.equal(rowsOf(fake, 'MockTests')[0].status, 'discarded');
  assert.equal(fake.values('Attempts').length, 1);
  assert.deepEqual(fake.values('MockTestItems'), [ITEM_HEADERS]);
});

// ---- Submit at zero seconds: goes through anyway

test('a zero-seconds submit goes through: a reset item is skipped, a dropped one is left out, the score is over the new count', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'], edit: ['q_dba0082ec68e'] });
  const res = server.submitMockTest([], 0, true);
  assert.equal(res.test_id, TEST_ID);
  assert.equal(res.unfinished, undefined);
  const attempts = rowsOf(fake, 'Attempts');
  assert.deepEqual(attempts.map((a) => [a.question_id, a.result]), [
    ['q_dba0082ec68e', 'skipped'], ['q_dfd5922f5aa9', 'correct'], ['q_8c09b37123eb', 'wrong'], ['q_c1db13ab836d', 'correct'],
  ]);
  assert.equal(attempts[0].selected, '');
  assert.equal(attempts[0].flagged, 'TRUE');
  assert.equal(attempts[0].question_updated_at, NEW_STAMP);
  const t = rowsOf(fake, 'MockTests')[0];
  assert.equal(t.status, 'submitted');
  assert.equal(t.question_count, '4');
  assert.equal(t.seconds_left, '0');
  assert.equal(t.correct_count, '2');
  assert.equal(t.score_pct, '50.0');
  assert.equal(res.test.skipped, 1);
  assert.deepEqual(fake.values('MockTestItems'), [ITEM_HEADERS]);
  // A skipped reset question moves no state; the dropped one has no row at all.
  assert.deepEqual(rowsOf(fake, 'QuestionState').map((s) => s.question_id).sort(), ['q_8c09b37123eb', 'q_c1db13ab836d', 'q_dfd5922f5aa9']);
  assert.deepEqual(res.notices, ['The bank changed during this test. 1 question was removed, the test now has 4. 1 question was edited and its answer was cleared.']);
  assert.deepEqual(res.resetRows.map((r) => r.id), ['q_dba0082ec68e']);
});

test('a zero-seconds submit that dropped every item discards the test', () => {
  const { fake, server } = running({ retire: Object.keys(ROW) });
  const res = server.submitMockTest([], 0, true);
  assert.equal(res.discarded, true);
  assert.equal(rowsOf(fake, 'MockTests')[0].status, 'discarded');
  assert.equal(fake.values('Attempts').length, 1);
});

test('the zero-seconds submit writes the sent changes first, then reconciles', () => {
  const { fake, server } = running({ retire: ['q_042896dc1966'] });
  server.submitMockTest([{ position: 5, selected: [], flagged: true }], 0, true);
  const a = rowsOf(fake, 'Attempts').find((r) => r.question_id === 'q_c1db13ab836d');
  assert.equal(a.result, 'skipped');
  assert.equal(a.flagged, 'TRUE');
});
