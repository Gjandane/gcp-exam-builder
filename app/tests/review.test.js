const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, setCell, settingsValues } = require('./bank-fixture.js');

// Fixture bank IDs in bank order (rows 2 to 13). Row 13 is retired.
const IDS = [
  'q_042896dc1966', 'q_dba0082ec68e', 'q_dfd5922f5aa9', 'q_8c09b37123eb', 'q_c1db13ab836d', 'q_01dc6054f16a',
  'q_bf7be128c7d4', 'q_f3bc82209733', 'q_4dc776a81b9a', 'q_4e90553f9801', 'q_8d26d2f8b050', 'q_b6b3be77081f',
];
const SINGLE_B = IDS[0]; // answer B, four choices
const MULTI_AC = IDS[1]; // answer A,C, four choices
const RETIRED = IDS[11];

const STATE_HEADERS = ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'];
const ATTEMPT_HEADERS = ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'];

// A set-up sheet: the fixture bank, valid Settings, and the given QuestionState
// and Attempts rows (arrays in header order). Today is 2026-11-18 in UTC.
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

// A QuestionState row in header order.
function stateRow(id, box, dueAt, lastSeenAt, extra = {}) {
  const row = {
    question_id: id, box: String(box), due_at: dueAt, attempts: '1', correct_count: '1', last_seen_at: lastSeenAt,
    last_result: 'correct', bookmarked: 'FALSE', note: '', note_updated_at: '', ...extra,
  };
  return STATE_HEADERS.map((h) => row[h]);
}

function attemptRow(answeredAt, id, selected, correctAnswer, result, extra = {}) {
  const row = {
    answered_at: answeredAt, question_id: id, mode: 'review', test_id: '', selected, correct_answer: correctAnswer,
    result, question_updated_at: '2026-11-01T10:00:00Z', flagged: '', ...extra,
  };
  return ATTEMPT_HEADERS.map((h) => row[h]);
}

function stateOf(fake, id) {
  const [headers, ...rows] = fake.values('QuestionState');
  const row = rows.find((r) => r[0] === id);
  if (!row) return undefined;
  const o = {};
  headers.forEach((h, i) => { o[h] = row[i]; });
  return o;
}

// ---- getReviewList: the All list

test('the All list holds active questions: unseen first in bank order, then seen by oldest last_seen_at', () => {
  const { server } = sheet({
    states: [
      stateRow(IDS[2], 2, '2026-11-25', '2026-11-15T09:00:00Z'),
      stateRow(IDS[0], 1, '2026-11-19', '2026-11-12T09:00:00Z'),
      stateRow(IDS[5], 3, '2026-11-30', '2026-11-15T09:00:00Z'), // ties IDS[2] on last_seen_at: bank order
      stateRow(IDS[7], 0, '', '', { bookmarked: 'TRUE', attempts: '0', correct_count: '0', last_result: '' }), // bookmark only: unseen
      stateRow(RETIRED, 1, '2026-11-19', '2026-11-01T09:00:00Z'),
      stateRow('q_gone00000000', 1, '2026-11-19', '2026-11-01T09:00:00Z'),
    ],
  });

  const result = server.getReviewList('all');

  assert.deepEqual(result.ids, [
    IDS[1], IDS[3], IDS[4], IDS[6], IDS[7], IDS[8], IDS[9], IDS[10],
    IDS[0], IDS[2], IDS[5],
  ]);
});

test('an unknown filter is refused', () => {
  const { server } = sheet();
  assert.equal(server.getReviewList('nope').error, 'unknown_filter');
});

// ---- getReviewList: Due, Wrong, Bookmarked and the counts

// Today is 2026-11-18, the exam is 2026-12-31 (no cap in play).
function filterSheet(extra = {}) {
  return sheet({
    states: [
      stateRow(IDS[0], 2, '2026-11-17', '2026-11-10T09:00:00Z'), // due, 1 day overdue
      stateRow(IDS[2], 1, '2026-11-18', '2026-11-17T09:00:00Z', { last_result: 'wrong' }), // due today, wrong, newest
      stateRow(IDS[3], 3, '2026-11-10', '2026-11-05T09:00:00Z', { last_result: 'wrong', bookmarked: 'TRUE' }), // due, most overdue, wrong, bookmarked
      stateRow(IDS[4], 2, '2026-11-25', '2026-11-16T09:00:00Z', { bookmarked: 'TRUE' }), // not due
      stateRow(IDS[5], 1, '2026-11-17', '2026-11-12T09:00:00Z'), // due, ties IDS[0] on due date: bank order
      stateRow(IDS[7], 0, '', '', { bookmarked: 'TRUE', attempts: '0', correct_count: '0', last_result: '' }), // bookmark only: unseen
      stateRow(RETIRED, 1, '2026-11-01', '2026-11-01T09:00:00Z', { last_result: 'wrong', bookmarked: 'TRUE' }),
      stateRow('q_gone00000000', 1, '2026-11-01', '2026-11-01T09:00:00Z', { last_result: 'wrong', bookmarked: 'TRUE' }),
    ],
    ...extra,
  });
}

test('the Due list holds seen, due questions, most overdue first, ties in bank order, unseen left out', () => {
  const { server } = filterSheet();
  assert.deepEqual(server.getReviewList('due').ids, [IDS[3], IDS[0], IDS[5], IDS[2]]);
});

test('the Wrong list holds last_result wrong, newest last_seen_at first, retired and missing IDs left out', () => {
  const { server } = filterSheet();
  assert.deepEqual(server.getReviewList('wrong').ids, [IDS[2], IDS[3]]);
});

test('the Wrong list breaks a last_seen_at tie in bank order', () => {
  const { server } = sheet({
    states: [
      stateRow(IDS[5], 1, '2026-11-19', '2026-11-17T09:00:00Z', { last_result: 'wrong' }),
      stateRow(IDS[2], 1, '2026-11-19', '2026-11-17T09:00:00Z', { last_result: 'wrong' }),
    ],
  });
  assert.deepEqual(server.getReviewList('wrong').ids, [IDS[2], IDS[5]]);
});

test('the Bookmarked list holds bookmarked active questions in bank order, seen or not', () => {
  const { server } = filterSheet();
  assert.deepEqual(server.getReviewList('bookmarked').ids, [IDS[3], IDS[4], IDS[7]]);
});

test('Due uses the capped due date: the day before the exam makes a far-off question due', () => {
  const { server } = sheet({
    settings: { exam_date: '2026-11-20' },
    states: [stateRow(IDS[0], 5, '2026-12-30', '2026-11-10T09:00:00Z')],
  });
  assert.deepEqual(server.getReviewList('due').ids, []);
  const later = sheet({
    now: '2026-11-19T08:00:00Z',
    settings: { exam_date: '2026-11-20' },
    states: [stateRow(IDS[0], 5, '2026-12-30', '2026-11-10T09:00:00Z')],
  });
  assert.deepEqual(later.server.getReviewList('due').ids, [IDS[0]]);
});

test('Due applies the changed-answer rule: a changed answer makes the question due', () => {
  const bank = fixtureBank();
  const { server } = sheet({
    bank,
    states: [stateRow(SINGLE_B, 3, '2026-12-20', '2026-11-10T09:00:00Z')],
    attempts: [attemptRow('2026-11-10T09:00:00Z', SINGLE_B, 'B', 'C', 'correct')], // last graded under answer C; bank says B
  });
  assert.deepEqual(server.getReviewList('due').ids, [SINGLE_B]);
});

test('the four counts match the four lists, in getReviewList and in load, retired and missing IDs left out', () => {
  const { server } = filterSheet();
  const expected = { all: 11, due: 4, wrong: 2, bookmarked: 3 };

  for (const filter of ['all', 'due', 'wrong', 'bookmarked']) {
    assert.deepEqual(server.getReviewList(filter).counts, expected, filter);
  }
  assert.deepEqual(server.load().counts, expected);
});

test('answerReview returns the four counts after the answer', () => {
  const { server } = filterSheet();

  // MULTI_AC is unseen: a wrong answer adds it to Wrong; it is due tomorrow, so not to Due.
  const wrong = server.answerReview(MULTI_AC, ['A', 'B']);
  assert.equal(wrong.result, 'wrong');
  assert.deepEqual(wrong.counts, { all: 11, due: 4, wrong: 3, bookmarked: 3 });

  // SINGLE_B is due; a correct answer moves it out of Due.
  const right = server.answerReview(SINGLE_B, ['B']);
  assert.equal(right.result, 'correct');
  assert.deepEqual(right.counts, { all: 11, due: 3, wrong: 3, bookmarked: 3 });
});

test('a wrong answer puts the question first on the Wrong list with the count up by one', () => {
  const { server } = filterSheet();
  const before = server.getReviewList('wrong');

  const answered = server.answerReview(SINGLE_B, ['C']);
  const after = server.getReviewList('wrong');

  assert.equal(answered.result, 'wrong');
  assert.equal(after.ids[0], SINGLE_B);
  assert.equal(after.counts.wrong, before.counts.wrong + 1);
});

// ---- answerReview: grading

test('a single-select pick equal to the answer is correct and appends one Attempts row with every column', () => {
  const { fake, server } = sheet({ now: '2026-11-18T08:30:00Z' });

  const result = server.answerReview(SINGLE_B, ['B']);

  assert.equal(result.result, 'correct');
  assert.equal(result.correctAnswer, 'B');
  assert.deepEqual(fake.values('Attempts'), [
    ATTEMPT_HEADERS,
    ['2026-11-18T08:30:00Z', SINGLE_B, 'review', '', 'B', 'B', 'correct', '2026-11-01T10:00:00Z', ''],
  ]);
});

test('a single-select wrong pick is wrong', () => {
  const { fake, server } = sheet();
  assert.equal(server.answerReview(SINGLE_B, ['C']).result, 'wrong');
  assert.equal(fake.values('Attempts')[1][4], 'C');
  assert.equal(fake.values('Attempts')[1][6], 'wrong');
});

test('a multi-select pick is graded as an exact set and stored sorted', () => {
  const { fake, server } = sheet();

  assert.equal(server.answerReview(MULTI_AC, ['C', 'A']).result, 'correct');
  assert.equal(server.answerReview(MULTI_AC, ['A', 'B']).result, 'wrong');

  const rows = fake.values('Attempts').slice(1);
  assert.equal(rows.length, 2, 'one row per answer');
  assert.deepEqual(rows.map((r) => [r[4], r[5], r[6]]), [['A,C', 'A,C', 'correct'], ['A,B', 'A,C', 'wrong']]);
});

test('the Attempts row records the bank row updated_at at grading', () => {
  const bank = setCell(fixtureBank(), 2, 'updated_at', '2026-11-10T07:00:00Z');
  const { fake, server } = sheet({ bank });
  server.answerReview(SINGLE_B, ['B']);
  assert.equal(fake.values('Attempts')[1][7], '2026-11-10T07:00:00Z');
});

test('a pick of the wrong size is wrong: a subset or a superset of the answer', () => {
  const { fake, server } = sheet();
  assert.equal(server.answerReview(MULTI_AC, ['A']).result, 'wrong');
  assert.equal(server.answerReview(SINGLE_B, ['B', 'C']).result, 'wrong');
  assert.deepEqual(fake.values('Attempts').slice(1).map((r) => [r[4], r[6]]), [['A', 'wrong'], ['B,C', 'wrong']]);
});

test('an empty pick, a bad letter, a repeated letter, a retired or unknown question is refused and writes nothing', () => {
  const { fake, server } = sheet();
  const cases = [
    [SINGLE_B, []],
    [SINGLE_B, ['E']], // no choice E on this row
    [SINGLE_B, ['Z']],
    [MULTI_AC, ['A', 'A']],
    [RETIRED, ['A']],
    ['q_unknown00000', ['A']],
    [SINGLE_B, 'B'],
  ];
  for (const [id, picks] of cases) {
    const result = server.answerReview(id, picks);
    assert.ok(result.error, 'refused: ' + id + ' ' + JSON.stringify(picks));
  }
  assert.deepEqual(fake.values('Attempts'), [ATTEMPT_HEADERS]);
  assert.deepEqual(fake.values('QuestionState'), [STATE_HEADERS]);
});

test('answerReview returns the busy error when the lock is held and writes nothing', () => {
  const { fake, server } = sheet();
  fake.holdLockElsewhere();
  assert.deepEqual(server.answerReview(SINGLE_B, ['B']), { error: 'busy', message: 'The sheet is busy. Try again.' });
  assert.deepEqual(fake.values('Attempts'), [ATTEMPT_HEADERS]);
});

// ---- answerReview: the Leitner table. Today is 2026-11-18, the exam 2026-12-31.

test('correct on an unseen question creates the row in box 1, due tomorrow, with the counters', () => {
  const { fake, server } = sheet({ now: '2026-11-18T08:30:00Z' });

  const result = server.answerReview(SINGLE_B, ['B']);

  const expected = {
    question_id: SINGLE_B, box: '1', due_at: '2026-11-19', attempts: '1', correct_count: '1',
    last_seen_at: '2026-11-18T08:30:00Z', last_result: 'correct', bookmarked: 'FALSE', note: '', note_updated_at: '',
  };
  assert.deepEqual(stateOf(fake, SINGLE_B), expected);
  assert.deepEqual(result.state, { ...expected, effective_box: 1, effective_due_at: '2026-11-19' });
});

test('wrong on an unseen question creates the row in box 1, due tomorrow, with no correct count', () => {
  const { fake, server } = sheet();
  server.answerReview(SINGLE_B, ['A']);
  const s = stateOf(fake, SINGLE_B);
  assert.deepEqual([s.box, s.due_at, s.attempts, s.correct_count, s.last_result], ['1', '2026-11-19', '1', '0', 'wrong']);
});

test('correct on a due question moves it one box up, due today plus the new interval', () => {
  const { fake, server } = sheet({
    states: [
      stateRow(IDS[0], 2, '2026-11-18', '2026-11-16T09:00:00Z'), // due today
      stateRow(IDS[2], 3, '2026-11-10', '2026-11-06T09:00:00Z'), // overdue
      stateRow(IDS[3], 5, '2026-11-17', '2026-11-01T09:00:00Z'), // box 5 stays 5
    ],
  });

  server.answerReview(IDS[0], ['B']);
  server.answerReview(IDS[2], ['A']);
  server.answerReview(IDS[3], ['B']);

  assert.deepEqual([stateOf(fake, IDS[0]).box, stateOf(fake, IDS[0]).due_at], ['3', '2026-11-22']);
  assert.deepEqual([stateOf(fake, IDS[2]).box, stateOf(fake, IDS[2]).due_at], ['4', '2026-11-26']);
  assert.deepEqual([stateOf(fake, IDS[3]).box, stateOf(fake, IDS[3]).due_at], ['5', '2026-12-04']);
});

test('correct on a seen question that is not due holds box and due_at but counts the attempt', () => {
  const { fake, server } = sheet({
    now: '2026-11-18T09:00:00Z',
    states: [stateRow(SINGLE_B, 3, '2026-11-25', '2026-11-17T09:00:00Z', { attempts: '4', correct_count: '2', last_result: 'wrong' })],
  });

  const result = server.answerReview(SINGLE_B, ['B']);

  assert.equal(result.result, 'correct');
  const s = stateOf(fake, SINGLE_B);
  assert.deepEqual(
    [s.box, s.due_at, s.attempts, s.correct_count, s.last_seen_at, s.last_result],
    ['3', '2026-11-25', '5', '3', '2026-11-18T09:00:00Z', 'correct'],
  );
});

test('wrong on any seen question sends it to box 1, due tomorrow', () => {
  const { fake, server } = sheet({
    states: [stateRow(SINGLE_B, 4, '2026-11-30', '2026-11-10T09:00:00Z', { attempts: '3', correct_count: '3' })],
  });
  server.answerReview(SINGLE_B, ['D']);
  const s = stateOf(fake, SINGLE_B);
  assert.deepEqual([s.box, s.due_at, s.attempts, s.correct_count, s.last_result], ['1', '2026-11-19', '4', '3', 'wrong']);
});

test('an answer keeps the bookmark, the note, other rows and an unknown column', () => {
  const { fake, server } = sheet({
    states: [
      stateRow(IDS[4], 2, '2026-11-20', '2026-11-12T09:00:00Z'),
      stateRow(SINGLE_B, 0, '', '', { bookmarked: 'TRUE', note: 'trap', note_updated_at: '2026-11-17T10:00:00Z', attempts: '0', correct_count: '0', last_result: '' }),
    ],
  });
  const values = fake.values('QuestionState');
  values[0].push('my_column');
  values[1].push('keep me');
  values[2].push('me too');
  fake.addTab('QuestionState', values);

  server.answerReview(SINGLE_B, ['B']);

  const after = fake.values('QuestionState');
  assert.deepEqual(after[1], values[1], 'the other row is untouched');
  assert.deepEqual(after[2], [SINGLE_B, '1', '2026-11-19', '1', '1', '2026-11-18T08:00:00Z', 'correct', 'TRUE', 'trap', '2026-11-17T10:00:00Z', 'me too']);
});

// ---- the exam-date cap

test('the cap makes a question due without a rewrite, and a correct answer stores the uncapped due date', () => {
  // Exam on 2026-11-19: the cap is 2026-11-18, today.
  const { fake, server } = sheet({
    settings: { exam_date: '2026-11-19' },
    states: [stateRow(SINGLE_B, 3, '2026-11-25', '2026-11-17T09:00:00Z')],
  });
  const before = fake.values('QuestionState');

  const home = server.load();

  assert.equal(home.screen, 'home');
  assert.equal(home.states[SINGLE_B].effective_box, 3);
  assert.equal(home.states[SINGLE_B].effective_due_at, '2026-11-18');
  assert.equal(home.states[SINGLE_B].due_at, '2026-11-25', 'the stored due_at comes along unchanged');
  assert.deepEqual(fake.values('QuestionState'), before, 'load writes nothing');

  const result = server.answerReview(SINGLE_B, ['B']);
  assert.deepEqual([stateOf(fake, SINGLE_B).box, stateOf(fake, SINGLE_B).due_at], ['4', '2026-11-26']);
  assert.equal(result.state.effective_due_at, '2026-11-18', 'the client gets the capped date');
});

test('the cap holds a due date to the day before the exam, and an exam-date edit moves it at once', () => {
  const { fake, server } = sheet({
    settings: { exam_date: '2026-11-22' },
    states: [stateRow(SINGLE_B, 4, '2026-11-26', '2026-11-17T09:00:00Z')],
  });
  assert.equal(server.load().states[SINGLE_B].effective_due_at, '2026-11-21');

  fake.addTab('Settings', settingsValues({ exam_date: '2026-11-25' }));
  assert.equal(server.load().states[SINGLE_B].effective_due_at, '2026-11-24');
  assert.equal(stateOf(fake, SINGLE_B).due_at, '2026-11-26');
});

test('on the exam day itself the cap makes every seen question due', () => {
  const { fake, server } = sheet({
    settings: { exam_date: '2026-11-18' },
    states: [stateRow(SINGLE_B, 2, '2026-11-20', '2026-11-17T09:00:00Z')],
  });
  assert.equal(server.load().states[SINGLE_B].effective_due_at, '2026-11-17');
  server.answerReview(SINGLE_B, ['B']);
  assert.equal(stateOf(fake, SINGLE_B).box, '3', 'due, so a correct answer moves it up');
});

test('the cap is off after the exam date', () => {
  const { fake, server } = sheet({
    settings: { exam_date: '2026-11-10' },
    states: [stateRow(SINGLE_B, 3, '2026-11-25', '2026-11-17T09:00:00Z')],
  });
  assert.equal(server.load().states[SINGLE_B].effective_due_at, '2026-11-25');
  server.answerReview(SINGLE_B, ['B']);
  assert.deepEqual([stateOf(fake, SINGLE_B).box, stateOf(fake, SINGLE_B).due_at], ['3', '2026-11-25'], 'not due: box held');
});

// ---- the changed-answer rule

test('a changed answer makes the question due today in box 1, and a correct answer then gives box 2', () => {
  // The bank says B; the last graded attempt was graded against C.
  const { fake, server } = sheet({
    states: [stateRow(SINGLE_B, 4, '2026-12-10', '2026-11-10T09:00:00Z')],
    attempts: [attemptRow('2026-11-10T09:00:00Z', SINGLE_B, 'C', 'C', 'correct')],
  });
  const before = fake.values('QuestionState');

  const home = server.load();
  assert.equal(home.states[SINGLE_B].effective_box, 1);
  assert.equal(home.states[SINGLE_B].effective_due_at, '2026-11-18');
  assert.deepEqual(fake.values('QuestionState'), before, 'read time only');

  const result = server.answerReview(SINGLE_B, ['B']);
  assert.deepEqual([stateOf(fake, SINGLE_B).box, stateOf(fake, SINGLE_B).due_at], ['2', '2026-11-20']);
  assert.equal(result.state.effective_box, 2, 'the new answer clears the rule');
  assert.equal(result.state.effective_due_at, '2026-11-20');
});

test('a skipped row carrying the new answer does not clear the changed-answer rule', () => {
  const { server } = sheet({
    states: [stateRow(SINGLE_B, 4, '2026-12-10', '2026-11-10T09:00:00Z')],
    attempts: [
      attemptRow('2026-11-10T09:00:00Z', SINGLE_B, 'C', 'C', 'correct'),
      attemptRow('2026-11-15T09:00:00Z', SINGLE_B, '', 'B', 'skipped', { mode: 'mock', test_id: 't_20261115T080000Z', flagged: 'FALSE' }),
    ],
  });
  const state = server.load().states[SINGLE_B];
  assert.deepEqual([state.effective_box, state.effective_due_at], [1, '2026-11-18']);
});

test('an answer equal to the last graded one keeps the stored state, letters compared as sets', () => {
  const { server } = sheet({
    states: [stateRow(MULTI_AC, 3, '2026-11-25', '2026-11-10T09:00:00Z')],
    attempts: [attemptRow('2026-11-10T09:00:00Z', MULTI_AC, 'C,A', 'C, A', 'correct')],
  });
  const state = server.load().states[MULTI_AC];
  assert.deepEqual([state.effective_box, state.effective_due_at], [3, '2026-11-25']);
});

// ---- load and time zones

test('load returns every state row with its effective box and due date; unseen rows have box 0', () => {
  const { server } = sheet({
    states: [
      stateRow(SINGLE_B, 2, '2026-11-20', '2026-11-12T09:00:00Z'),
      stateRow(MULTI_AC, 0, '', '', { bookmarked: 'TRUE', attempts: '0', correct_count: '0', last_result: '' }),
    ],
  });
  const states = server.load().states;
  assert.deepEqual(Object.keys(states).sort(), [MULTI_AC, SINGLE_B].sort());
  assert.deepEqual([states[SINGLE_B].effective_box, states[SINGLE_B].effective_due_at], [2, '2026-11-20']);
  assert.deepEqual([states[MULTI_AC].effective_box, states[MULTI_AC].effective_due_at], [0, '']);
});

test('today is the date in the spreadsheet time zone', () => {
  // 20:00 UTC on the 18th is the 19th in Kiritimati (UTC+14).
  const { fake, server } = sheet({ now: '2026-11-18T20:00:00Z', timeZone: 'Pacific/Kiritimati' });
  server.answerReview(SINGLE_B, ['A']);
  assert.equal(stateOf(fake, SINGLE_B).due_at, '2026-11-20');
  assert.equal(fake.values('Attempts')[1][0], '2026-11-18T20:00:00Z', 'answered_at stays UTC');
});
