const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, settingsValues } = require('./bank-fixture.js');

const IDS = [
  'q_042896dc1966', 'q_dba0082ec68e', 'q_dfd5922f5aa9', 'q_8c09b37123eb', 'q_c1db13ab836d', 'q_01dc6054f16a',
  'q_bf7be128c7d4', 'q_f3bc82209733', 'q_4dc776a81b9a', 'q_4e90553f9801', 'q_8d26d2f8b050', 'q_b6b3be77081f',
];
const RETIRED = IDS[11];
const NOW = '2026-11-18T08:00:00Z';

const STATE_HEADERS = ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'];
const ATTEMPT_HEADERS = ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'];

function sheet({ states = [] } = {}) {
  const fake = makeFakeAdapter({ now: NOW });
  fake.props.setup_done_at = '2026-11-01T00:00:00Z';
  fake.addTab('Questions', fixtureBank());
  fake.addTab('Settings', settingsValues({}), { plainText: true, frozenRows: 1 });
  fake.addTab('QuestionState', [STATE_HEADERS, ...states], { plainText: true, frozenRows: 1 });
  fake.addTab('Attempts', [ATTEMPT_HEADERS], { plainText: true, frozenRows: 1 });
  for (const [name, headers] of Object.entries({
    MockTests: ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'],
    MockTestItems: ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'],
    Reports: ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution'],
  })) fake.addTab(name, [headers], { plainText: true, frozenRows: 1 });
  return { fake, server: makeServer(fake.adapter) };
}

function stateRow(id, extra = {}) {
  const row = {
    question_id: id, box: '2', due_at: '2026-11-25', attempts: '1', correct_count: '1', last_seen_at: '2026-11-16T09:00:00Z',
    last_result: 'correct', bookmarked: 'FALSE', note: '', note_updated_at: '', ...extra,
  };
  return STATE_HEADERS.map((h) => row[h]);
}

function stateOf(fake, id) {
  const [headers, ...rows] = fake.values('QuestionState');
  const row = rows.find((r) => r[0] === id);
  if (!row) return undefined;
  const o = {};
  headers.forEach((h, i) => { o[h] = row[i]; });
  return o;
}

// ---- setBookmark

test('the first Bookmark on an unseen question creates a state row that stays unseen', () => {
  const { fake, server } = sheet();

  const res = server.setBookmark(IDS[3], true);

  assert.deepEqual(stateOf(fake, IDS[3]), {
    question_id: IDS[3], box: '0', due_at: '', attempts: '0', correct_count: '0',
    last_seen_at: '', last_result: '', bookmarked: 'TRUE', note: '', note_updated_at: '',
  });
  assert.equal(res.state.bookmarked, 'TRUE');
  assert.equal(res.state.box, '0');
  assert.equal(res.state.effective_box, 0);
  assert.equal(res.state.due_at, '');
});

test('a Bookmark raises the Bookmarked count by one and the other counts hold', () => {
  const { server } = sheet();
  const before = server.getReviewList('bookmarked').counts;

  const res = server.setBookmark(IDS[3], true);

  assert.deepEqual(res.counts, { ...before, bookmarked: before.bookmarked + 1 });
  assert.deepEqual(server.getReviewList('bookmarked').ids, [IDS[3]]);
});

test('toggling a Bookmark off writes FALSE and lowers the count', () => {
  const { fake, server } = sheet({ states: [stateRow(IDS[4], { bookmarked: 'TRUE' })] });
  assert.equal(server.getReviewList('bookmarked').counts.bookmarked, 1);

  const res = server.setBookmark(IDS[4], false);

  assert.equal(stateOf(fake, IDS[4]).bookmarked, 'FALSE');
  assert.equal(res.counts.bookmarked, 0);
});

test('a Bookmark on a seen question keeps its box, due date and counters', () => {
  const { fake, server } = sheet({ states: [stateRow(IDS[4])] });

  server.setBookmark(IDS[4], true);

  const row = stateOf(fake, IDS[4]);
  assert.deepEqual([row.box, row.due_at, row.attempts, row.correct_count, row.last_result], ['2', '2026-11-25', '1', '1', 'correct']);
});

test('a Bookmark on a retired or missing question is refused and writes nothing', () => {
  const { fake, server } = sheet();
  assert.equal(server.setBookmark(RETIRED, true).error, 'bad_mark');
  assert.equal(server.setBookmark('q_gone00000000', true).error, 'bad_mark');
  assert.equal(fake.values('QuestionState').length, 1);
});

// ---- saveNote

test('saveNote writes note and note_updated_at and creates an unseen row when absent', () => {
  const { fake, server } = sheet();

  const res = server.saveNote(IDS[2], 'watch the trap');

  const row = stateOf(fake, IDS[2]);
  assert.equal(row.note, 'watch the trap');
  assert.equal(row.note_updated_at, NOW);
  assert.equal(row.box, '0');
  assert.equal(row.due_at, '');
  assert.equal(row.bookmarked, 'FALSE');
  assert.equal(res.state.note, 'watch the trap');
});

test('saveNote caps the note at 1,000 characters', () => {
  const { fake, server } = sheet();
  server.saveNote(IDS[2], 'x'.repeat(1500));
  assert.equal(stateOf(fake, IDS[2]).note.length, 1000);
});

test('an empty note clears the note and still stamps note_updated_at', () => {
  const { fake, server } = sheet({ states: [stateRow(IDS[2], { note: 'old', note_updated_at: '2026-11-10T00:00:00Z' })] });

  server.saveNote(IDS[2], '');

  const row = stateOf(fake, IDS[2]);
  assert.equal(row.note, '');
  assert.equal(row.note_updated_at, NOW);
});

test('a note keeps the bookmark and the SR fields of a seen question', () => {
  const { fake, server } = sheet({ states: [stateRow(IDS[4], { bookmarked: 'TRUE' })] });

  server.saveNote(IDS[4], 'mnemonic');

  const row = stateOf(fake, IDS[4]);
  assert.deepEqual([row.bookmarked, row.box, row.due_at, row.attempts], ['TRUE', '2', '2026-11-25', '1']);
});

test('saveNote refuses a retired question and a non-text note', () => {
  const { server } = sheet();
  assert.equal(server.saveNote(RETIRED, 'x').error, 'bad_mark');
  assert.equal(server.saveNote(IDS[0], 5).error, 'bad_mark');
});

test('a noted unseen question stays in the All list as unseen and not due', () => {
  const { server } = sheet();
  server.saveNote(IDS[2], 'n');
  const counts = server.getReviewList('all').counts;
  assert.equal(counts.due, 0);
  assert.equal(server.getReviewList('all').ids[0], IDS[0]);
});

test('setBookmark refuses a non-boolean flag and writes nothing', () => {
  const { fake, server } = sheet();
  assert.equal(server.setBookmark(IDS[0], 'maybe').error, 'bad_mark');
  assert.equal(fake.values('QuestionState').length, 1);
});
