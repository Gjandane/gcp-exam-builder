const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, setCell, settingsValues } = require('./bank-fixture.js');

// Fixture bank IDs in bank order: answer B, answer A,C, and a third question.
const [SINGLE_B, MULTI_AC, THIRD] = ['q_042896dc1966', 'q_dba0082ec68e', 'q_dfd5922f5aa9'];
const CACHE_FIELDS = ['box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result'];
const STATE_HEADERS = ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'];
const ATTEMPT_HEADERS = ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'];

function sheet({ now = '2026-11-18T08:00:00Z', timeZone, settings = {}, states = [], attempts = [], bank = fixtureBank() } = {}) {
  const fake = makeFakeAdapter({ now, timeZone });
  fake.props.setup_done_at = '2026-11-01T00:00:00Z';
  fake.addTab('Questions', bank);
  fake.addTab('Settings', settingsValues(settings), { plainText: true, frozenRows: 1 });
  fake.addTab('QuestionState', [STATE_HEADERS, ...states], { plainText: true, frozenRows: 1 });
  fake.addTab('Attempts', [ATTEMPT_HEADERS, ...attempts], { plainText: true, frozenRows: 1 });
  for (const [name, headers] of Object.entries({
    MockTests: ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'],
    MockTestItems: ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'],
    Reports: ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution'],
  })) fake.addTab(name, [headers], { plainText: true, frozenRows: 1 });
  return { fake, server: makeServer(fake.adapter) };
}

function attemptRow(answeredAt, id, selected, correctAnswer, result, extra = {}) {
  const row = {
    answered_at: answeredAt, question_id: id, mode: 'review', test_id: '', selected, correct_answer: correctAnswer,
    result, question_updated_at: '2026-11-01T10:00:00Z', flagged: '', ...extra,
  };
  return ATTEMPT_HEADERS.map((h) => row[h]);
}

function stateRow(id, fields) {
  const row = {
    question_id: id, box: '0', due_at: '', attempts: '0', correct_count: '0', last_seen_at: '', last_result: '',
    bookmarked: 'FALSE', note: '', note_updated_at: '', ...fields,
  };
  return STATE_HEADERS.map((h) => row[h]);
}

// QuestionState as {question_id: row object}.
function states(fake) {
  const [headers, ...rows] = fake.values('QuestionState');
  const out = {};
  for (const r of rows) {
    const o = {};
    headers.forEach((h, i) => { o[h] = r[i]; });
    out[o.question_id] = o;
  }
  return out;
}

function cacheOf(row) {
  return Object.fromEntries(CACHE_FIELDS.map((f) => [f, row[f]]));
}

function allCaches(map) {
  return Object.fromEntries(Object.entries(map).map(([id, row]) => [id, cacheOf(row)]));
}

test('a replay gives the same SR fields the live path gave, a changed answer included', () => {
  const { fake, server } = sheet({ settings: { exam_date: '2027-06-30' } });
  const live = (at, id, picks) => { fake.setNow(at); return server.answerReview(id, picks); };

  live('2026-11-18T08:00:00Z', SINGLE_B, ['B']); // unseen, correct: box 1
  live('2026-11-19T08:00:00Z', SINGLE_B, ['B']); // due, correct: box 2
  live('2026-11-20T08:00:00Z', SINGLE_B, ['B']); // not due, correct: held
  live('2026-11-21T08:00:00Z', SINGLE_B, ['A']); // wrong: box 1
  live('2026-11-21T09:00:00Z', MULTI_AC, ['A', 'C']);
  live('2026-11-22T08:00:00Z', MULTI_AC, ['A']); // wrong
  // The bank changes the answer of SINGLE_B to C.
  fake.addTab('Questions', setCell(fixtureBank(), 2, 'answer', 'C'));
  live('2026-11-23T08:00:00Z', SINGLE_B, ['C']); // changed answer: from box 1 and due, so box 2
  live('2026-11-24T08:00:00Z', SINGLE_B, ['C']); // box 2 due 11-25: not due, held
  // A skipped mock row sits in the log and changes nothing.
  fake.adapter.tabs.append('Attempts', [{
    answered_at: '2026-11-25T08:00:00Z', question_id: SINGLE_B, mode: 'mock', test_id: 't_1', selected: '', correct_answer: 'C', result: 'skipped',
    question_updated_at: '2026-11-01T10:00:00Z', flagged: 'FALSE',
  }]);

  const liveCaches = allCaches(states(fake));
  assert.equal(liveCaches[SINGLE_B].box, '2', 'sanity: the changed answer started over');
  assert.equal(server.rebuildState(), 2);
  assert.deepEqual(allCaches(states(fake)), liveCaches);
});

test('a row whose correct_answer differs from the previous non-skipped row starts from box 1 and due', () => {
  const { fake, server } = sheet({
    states: [stateRow(SINGLE_B, { box: '5', due_at: '2027-01-01' })],
    attempts: [
      attemptRow('2026-11-10T09:00:00Z', SINGLE_B, 'C', 'C', 'correct'), // box 1
      attemptRow('2026-11-11T09:00:00Z', SINGLE_B, 'C', 'C', 'correct'), // box 2, due 11-13
      attemptRow('2026-11-12T09:00:00Z', SINGLE_B, '', 'B', 'skipped', { mode: 'mock', test_id: 't_1' }),
      attemptRow('2026-11-12T10:00:00Z', SINGLE_B, 'B', 'B', 'correct'), // answer changed vs 11-11: box 2, due 11-14
    ],
  });
  assert.equal(server.rebuildState(), 1);
  assert.deepEqual(cacheOf(states(fake)[SINGLE_B]), {
    box: '2', due_at: '2026-11-14', attempts: '3', correct_count: '3', last_seen_at: '2026-11-12T10:00:00Z', last_result: 'correct',
  });
});

test('dates come from answered_at in the spreadsheet time zone, and due is uncapped', () => {
  // 23:30 UTC is already the next day in Auckland. The exam date is near, but the cap is not applied.
  const { fake, server } = sheet({
    timeZone: 'Pacific/Auckland',
    settings: { exam_date: '2026-11-20' },
    attempts: [
      attemptRow('2026-11-18T23:30:00Z', SINGLE_B, 'B', 'B', 'correct'), // 11-19 Auckland: box 1, due 11-20
      attemptRow('2026-11-20T23:30:00Z', SINGLE_B, 'B', 'B', 'correct'), // 11-21 Auckland: due, box 2, due 11-23
    ],
  });
  server.rebuildState();
  const row = states(fake)[SINGLE_B];
  assert.deepEqual([row.box, row.due_at], ['2', '2026-11-23']);
});

test('rebuild rewrites every row, adds missing rows, keeps bookmarks and notes, and returns the count', () => {
  const { fake, server } = sheet({
    states: [
      stateRow(SINGLE_B, { box: '5', due_at: '2030-01-01', attempts: '9', correct_count: '9', last_seen_at: 'x', last_result: 'wrong', bookmarked: 'TRUE', note: 'my note', note_updated_at: '2026-11-02T00:00:00Z' }),
      stateRow(THIRD, { bookmarked: 'TRUE', note: 'only a bookmark' }),
    ],
    attempts: [
      attemptRow('2026-11-10T09:00:00Z', SINGLE_B, 'B', 'B', 'correct'),
      attemptRow('2026-11-10T10:00:00Z', MULTI_AC, 'A', 'A,C', 'wrong'),
    ],
  });
  const attemptsBefore = fake.values('Attempts');

  assert.equal(server.rebuildState(), 3);

  const map = states(fake);
  assert.deepEqual(cacheOf(map[SINGLE_B]), {
    box: '1', due_at: '2026-11-11', attempts: '1', correct_count: '1', last_seen_at: '2026-11-10T09:00:00Z', last_result: 'correct',
  });
  assert.deepEqual([map[SINGLE_B].bookmarked, map[SINGLE_B].note, map[SINGLE_B].note_updated_at], ['TRUE', 'my note', '2026-11-02T00:00:00Z']);
  assert.deepEqual(cacheOf(map[MULTI_AC]), {
    box: '1', due_at: '2026-11-11', attempts: '1', correct_count: '0', last_seen_at: '2026-11-10T10:00:00Z', last_result: 'wrong',
  });
  assert.equal(map[MULTI_AC].bookmarked, 'FALSE', 'an added row starts unbookmarked');
  assert.deepEqual(cacheOf(map[THIRD]), { box: '0', due_at: '', attempts: '0', correct_count: '0', last_seen_at: '', last_result: '' }, 'no attempts means unseen');
  assert.deepEqual([map[THIRD].bookmarked, map[THIRD].note], ['TRUE', 'only a bookmark']);
  assert.deepEqual(fake.values('Attempts'), attemptsBefore, 'Attempts is never edited');
});

test('rebuild reports busy when the lock is not free', () => {
  const { fake, server } = sheet();
  fake.holdLockElsewhere();
  assert.equal(server.rebuildState().error, 'busy');
});

test('a load that recreates QuestionState on a sheet with Attempts rows rebuilds and warns', () => {
  const { fake, server } = sheet({
    attempts: [
      attemptRow('2026-11-10T09:00:00Z', SINGLE_B, 'B', 'B', 'correct'),
      attemptRow('2026-11-11T09:00:00Z', SINGLE_B, 'B', 'B', 'correct'),
    ],
  });
  fake.removeTab('QuestionState');

  const home = server.load();

  assert.equal(home.screen, 'home');
  const warning = home.warnings.find((w) => w.id === 'state_rebuilt');
  assert.equal(warning.text, 'The QuestionState tab was missing. Boxes and due dates were rebuilt from your attempts. Bookmarks and notes could not be recovered.');
  assert.deepEqual(cacheOf(states(fake)[SINGLE_B]), {
    box: '2', due_at: '2026-11-13', attempts: '2', correct_count: '2', last_seen_at: '2026-11-11T09:00:00Z', last_result: 'correct',
  });
  assert.equal(home.states[SINGLE_B].box, '2');
  assert.equal(server.load().warnings.some((w) => w.id === 'state_rebuilt'), false, 'the banner is for that load only');
});

test('a recreated QuestionState with an empty Attempts tab is not rebuilt and does not warn', () => {
  const { fake, server } = sheet();
  fake.removeTab('QuestionState');
  const home = server.load();
  assert.equal(home.screen, 'home');
  assert.equal(home.warnings.some((w) => w.id === 'state_rebuilt'), false);
  assert.deepEqual(fake.values('QuestionState'), [STATE_HEADERS]);
});
