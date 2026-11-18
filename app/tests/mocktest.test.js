const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, settingsValues } = require('./bank-fixture.js');

const STATE_HEADERS = ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'];
const ATTEMPT_HEADERS = ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'];
const TEST_HEADERS = ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'];
const ITEM_HEADERS = ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'];
const TODAY = '2026-11-18';

// A generated bank. `layout` maps a Subdomain to its number of active
// questions, e.g. {'1.1': 3, '2.1': 2}. IDs are q_<subdomain>_<n>, answer A.
function makeBank(layout, retired = {}) {
  const headers = fixtureBank()[0];
  const rows = [headers];
  const add = (sub, n, status) => {
    const o = {
      id: `q_${sub}_${status === 'retired' ? 'r' : ''}${n}`, exam: 'fixture', status, subdomain: sub, subdomain_title: 'Title ' + sub,
      question: 'Question ' + n, choice_a: 'one', choice_b: 'two', choice_c: 'three', choice_d: 'four', answer: 'A',
      updated_at: '2026-11-01T10:00:00Z',
    };
    rows.push(headers.map((h) => (o[h] === undefined ? '' : o[h])));
  };
  for (const [sub, count] of Object.entries(layout)) for (let i = 1; i <= count; i++) add(sub, i, 'active');
  for (const [sub, count] of Object.entries(retired)) for (let i = 1; i <= count; i++) add(sub, i, 'retired');
  return rows;
}

function sheet({ bank = fixtureBank(), settings = {}, states = [], attempts = [], tests = [], items = [], seed = 1 } = {}) {
  const fake = makeFakeAdapter({ now: TODAY + 'T08:00:00Z', seed });
  fake.props.setup_done_at = '2026-11-01T00:00:00Z';
  fake.addTab('Questions', bank);
  fake.addTab('Settings', settingsValues(settings), { plainText: true, frozenRows: 1 });
  fake.addTab('QuestionState', [STATE_HEADERS, ...states], { plainText: true, frozenRows: 1 });
  fake.addTab('Attempts', [ATTEMPT_HEADERS, ...attempts], { plainText: true, frozenRows: 1 });
  fake.addTab('MockTests', [TEST_HEADERS, ...tests], { plainText: true, frozenRows: 1 });
  fake.addTab('MockTestItems', [ITEM_HEADERS, ...items], { plainText: true, frozenRows: 1 });
  fake.addTab('Reports', [['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution']], { plainText: true, frozenRows: 1 });
  return { fake, server: makeServer(fake.adapter) };
}

function rowsOf(fake, name) {
  const [headers, ...rows] = fake.values(name);
  return rows.map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i]])));
}

function stateRow(id, box, dueAt, lastSeenAt) {
  const o = { question_id: id, box: String(box), due_at: dueAt, attempts: '1', correct_count: '1', last_seen_at: lastSeenAt, last_result: 'correct', bookmarked: 'FALSE', note: '', note_updated_at: '' };
  return STATE_HEADERS.map((h) => o[h]);
}

function attemptRow(id, result, extra = {}) {
  const o = { answered_at: '2026-11-10T08:00:00Z', question_id: id, mode: 'review', test_id: '', selected: result === 'skipped' ? '' : 'A', correct_answer: 'A', result, question_updated_at: '2026-11-01T10:00:00Z', flagged: '', ...extra };
  return ATTEMPT_HEADERS.map((h) => o[h]);
}

// Sampled question IDs of the started test, in position order.
function sampledIds(fake) {
  return rowsOf(fake, 'MockTestItems').map((r) => r.question_id);
}

function subOf(id) {
  return id.split('_')[1];
}

function countBy(ids, key) {
  const out = {};
  for (const id of ids) out[key(id)] = (out[key(id)] || 0) + 1;
  return out;
}

const sectionCounts = (ids) => countBy(ids, (id) => subOf(id).split('.')[0]);

function start(opts, count, minutes = 60) {
  const s = sheet(opts);
  const result = s.server.startMockTest(count, minutes);
  return { ...s, result, ids: sampledIds(s.fake) };
}

// ---- Start writes the rows

test('start appends one in_progress MockTests row and writes one item per question', () => {
  const { fake, result } = start({}, 5, 12);
  const tests = rowsOf(fake, 'MockTests');
  assert.equal(tests.length, 1);
  assert.deepEqual(tests[0], {
    test_id: 't_20261118T080000Z', status: 'in_progress', started_at: '2026-11-18T08:00:00Z', submitted_at: '',
    question_count: '5', minutes_allowed: '12', seconds_left: '720', correct_count: '', score_pct: '',
  });
  const items = rowsOf(fake, 'MockTestItems');
  assert.equal(items.length, 5);
  items.forEach((item, i) => {
    assert.equal(item.test_id, 't_20261118T080000Z');
    assert.equal(item.position, String(i + 1));
    assert.equal(item.selected, '');
    assert.equal(item.flagged, 'FALSE');
    assert.equal(item.question_updated_at, '2026-11-01T10:00:00Z');
  });
  assert.equal(new Set(items.map((r) => r.question_id)).size, 5);
  assert.equal(result.test.question_count, 5);
  assert.equal(result.test.seconds_left, 720);
  assert.equal(result.test.answered, 0);
  assert.equal(result.test.flagged, 0);
  assert.deepEqual(result.notices, []);
  assert.equal(rowsOf(fake, 'Attempts').length, 0);
});

test('choice_order is a shuffle of the filled stored letters of each question', () => {
  const bank = fixtureBank();
  const { fake } = start({ bank, settings: { section_weights: '' } }, 11);
  const byId = Object.fromEntries(bank.slice(1).map((r) => [r[0], r]));
  const h = bank[0];
  let moved = 0;
  for (const item of rowsOf(fake, 'MockTestItems')) {
    const q = byId[item.question_id];
    const filled = ['A', 'B', 'C', 'D', 'E', 'F'].filter((l) => q[h.indexOf('choice_' + l.toLowerCase())] !== '');
    assert.deepEqual(item.choice_order.split('').sort(), filled, item.question_id);
    if (item.choice_order !== filled.join('')) moved++;
  }
  assert.ok(moved > 0, 'some choice order is shuffled');
});

test('question order is shuffled, and the same seed gives the same rows', () => {
  // All due in one Subdomain: pick order is bank order, so only the final shuffle moves them.
  const a = start({ seed: 7, ...poolSheet(15, 0, 0) }, 15);
  const b = start({ seed: 7, ...poolSheet(15, 0, 0) }, 15);
  assert.deepEqual(a.fake.values('MockTestItems'), b.fake.values('MockTestItems'));
  const bankOrder = makeBank({ '1.1': 15 }).slice(1).map((r) => r[0]);
  assert.notDeepEqual(a.ids, bankOrder);
  assert.deepEqual(a.ids.slice().sort(), bankOrder.slice().sort());
});

test('start uses the given count and minutes and leaves Settings unchanged', () => {
  const s = sheet({ settings: { mock_question_count: '10', mock_minutes: '120' } });
  const before = s.fake.values('Settings');
  s.server.startMockTest(3, 7);
  assert.deepEqual(s.fake.values('Settings'), before);
  const row = rowsOf(s.fake, 'MockTests')[0];
  assert.equal(row.question_count, '3');
  assert.equal(row.minutes_allowed, '7');
  assert.equal(row.seconds_left, '420');
});

test('start refuses a count or minutes out of range and writes nothing', () => {
  for (const [count, minutes] of [[0, 60], [201, 60], [2.5, 60], ['x', 60], [5, 0], [5, 601], [5, 1.5]]) {
    const s = sheet();
    const result = s.server.startMockTest(count, minutes);
    assert.equal(result.error, 'bad_start', `${count}, ${minutes}`);
    assert.equal(rowsOf(s.fake, 'MockTests').length, 0);
    assert.equal(rowsOf(s.fake, 'MockTestItems').length, 0);
  }
  assert.equal(sheet().server.startMockTest(200, 600).error, undefined);
});

test('a second start is refused while a test is in_progress', () => {
  const s = sheet();
  s.server.startMockTest(5, 10);
  const items = s.fake.values('MockTestItems');
  s.fake.setNow('2026-11-18T09:00:00Z');
  const second = s.server.startMockTest(3, 10);
  assert.equal(second.error, 'in_progress');
  assert.equal(rowsOf(s.fake, 'MockTests').length, 1);
  assert.deepEqual(s.fake.values('MockTestItems'), items);
});

test('start is refused when the lock is busy', () => {
  const s = sheet();
  s.fake.holdLockElsewhere();
  assert.equal(s.server.startMockTest(5, 10).error, 'busy');
  assert.equal(rowsOf(s.fake, 'MockTests').length, 0);
});

// ---- Sampler: candidates

test('no retired or missing ID is sampled and no question twice; a short bank gives a shorter test with the notice', () => {
  const { fake, ids, result } = start({
    settings: { section_weights: '' },
    states: [stateRow('q_gone00000000', 1, '2026-11-01', '2026-11-01T08:00:00Z')],
  }, 200);
  const active = fixtureBank().slice(1).filter((r) => r[2] === 'active').map((r) => r[0]);
  assert.equal(ids.length, 11);
  assert.deepEqual(ids.slice().sort(), active.slice().sort());
  assert.equal(rowsOf(fake, 'MockTests')[0].question_count, '11');
  assert.deepEqual(result.notices, ['This test has 11 questions, not 200: the bank has only 11 active questions.']);
});

// ---- Sampler: Section split

test('the Section split follows the weights with largest-remainder rounding', () => {
  const bank = makeBank({ '1.1': 10, '2.1': 10, '3.1': 10 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '1:40,2:40,3:20' } }, 7).ids), { 1: 3, 2: 3, 3: 1 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '1:13,2:16,3:72' } }, 10).ids), { 1: 1, 2: 2, 3: 7 });
});

test('a remainder tie goes to the higher weight, then the lower Section number', () => {
  const bank = makeBank({ '1.1': 10, '2.1': 10, '3.1': 10 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '1:1,2:3,3:0' } }, 2).ids), { 2: 2 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '1:1,2:1,3:1' } }, 10).ids), { 1: 4, 2: 3, 3: 3 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '1:1,2:1,3:1' } }, 11).ids), { 1: 4, 2: 4, 3: 3 });
});

test('decimal weights round exactly', () => {
  const bank = makeBank({ '1.1': 10, '2.1': 10 });
  // 0.1 and 0.2 scale to 1 and 2: shares 1 and 2 with no float error.
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '1:0.1,2:0.2' } }, 3).ids), { 1: 1, 2: 2 });
});

test('Section numbers sort as numbers in the tie rule', () => {
  const bank = makeBank({ '10.1': 5, '2.1': 5 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '2:1,10:1' } }, 1).ids), { 2: 1 });
});

test('weight 0 leaves a Section out of the test', () => {
  const bank = makeBank({ '1.1': 10, '2.1': 10, '3.1': 10 });
  const { ids } = start({ bank, settings: { section_weights: '1:1,2:0,3:1' } }, 30);
  assert.deepEqual(sectionCounts(ids), { 1: 10, 3: 10 });
});

test('empty weights follow the bank\'s own proportions of active questions', () => {
  const bank = makeBank({ '1.1': 6, '2.1': 3, '3.1': 1 }, { '3.1': 5 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '' } }, 5).ids), { 1: 3, 2: 2 });
});

test('a short Section takes all it has and its shortfall goes to the others by weight', () => {
  const bank = makeBank({ '1.1': 10, '2.1': 10, '3.1': 2 });
  assert.deepEqual(sectionCounts(start({ bank, settings: { section_weights: '1:1,2:1,3:1' } }, 12).ids), { 1: 5, 2: 5, 3: 2 });
  // A weighted Section with only retired rows has no candidates: its share moves on.
  const bank2 = makeBank({ '1.1': 10, '2.1': 10 }, { '3.1': 3 });
  assert.deepEqual(sectionCounts(start({ bank: bank2, settings: { section_weights: '1:1,2:3,3:4' } }, 8).ids), { 1: 2, 2: 6 });
  // Two short Sections: the second round gives all 4 open slots to Section 2.
  const bank3 = makeBank({ '1.1': 3, '2.1': 20, '3.1': 1 });
  assert.deepEqual(sectionCounts(start({ bank: bank3, settings: { section_weights: '1:1,2:1,3:1' } }, 12).ids), { 1: 3, 2: 8, 3: 1 });
});

// ---- Sampler: buckets, pick orders, spill

// One Section, one Subdomain: `due` due questions, `weak` seen not due, `unseen` unseen.
function poolSheet(due, weak, unseen) {
  const layout = { '1.1': due + weak + unseen };
  const states = [];
  for (let i = 1; i <= due; i++) states.push(stateRow(`q_1.1_${i}`, 2, `2026-11-${String(i).padStart(2, '0')}`, '2026-11-01T08:00:00Z'));
  for (let i = due + 1; i <= due + weak; i++) states.push(stateRow(`q_1.1_${i}`, 3, '2026-12-20', '2026-11-05T08:00:00Z'));
  return { bank: makeBank(layout), states, settings: { section_weights: '' } };
}

function poolCounts(ids, due, weak) {
  return countBy(ids, (id) => {
    const n = +id.split('_')[2];
    return n <= due ? 'due' : n <= due + weak ? 'weak' : 'unseen';
  });
}

test('buckets split 40/30/30 with largest remainder, ties to due then weak-fill then unseen', () => {
  assert.deepEqual(poolCounts(start(poolSheet(10, 10, 10), 10).ids, 10, 10), { due: 4, weak: 3, unseen: 3 });
  // 5: 2.0 / 1.5 / 1.5 → the tie goes to weak-fill before unseen.
  assert.deepEqual(poolCounts(start(poolSheet(10, 10, 10), 5).ids, 10, 10), { due: 2, weak: 2, unseen: 1 });
  // 1: 0.4 / 0.3 / 0.3 → due.
  assert.deepEqual(poolCounts(start(poolSheet(10, 10, 10), 1).ids, 10, 10), { due: 1 });
  // 3: 1.2 / 0.9 / 0.9 → floors 1/0/0, remainders .2/.9/.9: weak-fill then unseen.
  assert.deepEqual(poolCounts(start(poolSheet(10, 10, 10), 3).ids, 10, 10), { due: 1, weak: 1, unseen: 1 });
});

test('due picks most overdue first, ties in bank order', () => {
  const bank = makeBank({ '1.1': 5 });
  const states = [
    stateRow('q_1.1_1', 2, '2026-11-17', '2026-11-01T08:00:00Z'),
    stateRow('q_1.1_2', 2, '2026-11-12', '2026-11-01T08:00:00Z'),
    stateRow('q_1.1_3', 2, '2026-11-15', '2026-11-01T08:00:00Z'),
    stateRow('q_1.1_4', 2, '2026-11-12', '2026-11-01T08:00:00Z'),
    stateRow('q_1.1_5', 2, '2026-11-18', '2026-11-01T08:00:00Z'),
  ];
  const take = (n) => start({ bank, states, settings: { section_weights: '' } }, n).ids.slice().sort();
  assert.deepEqual(take(1), ['q_1.1_2']);
  assert.deepEqual(take(2), ['q_1.1_2', 'q_1.1_4']);
  assert.deepEqual(take(3), ['q_1.1_2', 'q_1.1_3', 'q_1.1_4']);
});

test('weak-fill picks lowest box, then oldest last_seen_at, then bank order', () => {
  const bank = makeBank({ '1.1': 6 });
  const states = [
    stateRow('q_1.1_1', 4, '2026-12-20', '2026-11-01T08:00:00Z'),
    stateRow('q_1.1_2', 2, '2026-12-20', '2026-11-09T08:00:00Z'),
    stateRow('q_1.1_3', 2, '2026-12-20', '2026-11-03T08:00:00Z'),
    stateRow('q_1.1_4', 3, '2026-12-20', '2026-11-01T08:00:00Z'),
    stateRow('q_1.1_5', 2, '2026-12-20', '2026-11-03T08:00:00Z'),
    stateRow('q_1.1_6', 5, '2026-12-20', '2026-11-01T08:00:00Z'),
  ];
  // Box 2 first (3 and 5 tie on last_seen_at: bank order, then 2), then box 3.
  const take = (n) => start({ bank, states, settings: { section_weights: '' } }, n).ids.slice().sort();
  assert.deepEqual(take(2), ['q_1.1_3', 'q_1.1_5']);
  assert.deepEqual(take(3), ['q_1.1_2', 'q_1.1_3', 'q_1.1_5']);
  assert.deepEqual(take(4), ['q_1.1_2', 'q_1.1_3', 'q_1.1_4', 'q_1.1_5']);
});

test('due and weak-fill pools use the exam-date cap and the changed-answer rule', () => {
  const bank = makeBank({ '1.1': 4 });
  const states = [
    stateRow('q_1.1_1', 3, '2026-12-30', '2026-11-01T08:00:00Z'), // capped to 2026-11-19: not due
    stateRow('q_1.1_2', 3, '2026-12-30', '2026-11-01T08:00:00Z'), // answer changed: due
    stateRow('q_1.1_3', 3, '2026-12-30', '2026-11-01T08:00:00Z'),
    stateRow('q_1.1_4', 3, '2026-12-30', '2026-11-01T08:00:00Z'),
  ];
  const attempts = [attemptRow('q_1.1_2', 'correct', { correct_answer: 'B', selected: 'B' })];
  const { ids } = start({ bank, states, attempts, settings: { section_weights: '', exam_date: '2026-11-20' } }, 1);
  assert.deepEqual(ids, ['q_1.1_2']);
  // Exam tomorrow: the cap is today, so every seen question is due without a rewrite.
  const capped = start({ bank, states, settings: { section_weights: '', exam_date: '2026-11-19' } }, 1);
  // All due on the same capped date: the tie goes to bank order.
  assert.deepEqual(capped.ids, ['q_1.1_1']);
});

test('spill passes a short pool\'s slots to due, then weak-fill, then unseen', () => {
  // Quotas 4/3/3. Due has 2: its 2 open slots go to weak-fill, not unseen.
  assert.deepEqual(poolCounts(start(poolSheet(2, 5, 5), 10).ids, 2, 5), { due: 2, weak: 5, unseen: 3 });
  // Unseen has 1: its 2 open slots go to due first.
  assert.deepEqual(poolCounts(start(poolSheet(10, 10, 1), 10).ids, 10, 10), { due: 6, weak: 3, unseen: 1 });
  // Weak-fill has 0: its 3 open slots go to due.
  assert.deepEqual(poolCounts(start(poolSheet(10, 0, 10), 10).ids, 10, 0), { due: 7, unseen: 3 });
  // Due and weak-fill short: the rest comes from unseen.
  assert.deepEqual(poolCounts(start(poolSheet(1, 1, 10), 10).ids, 1, 1), { due: 1, weak: 1, unseen: 8 });
});

test('unseen picks are random but fixed by the seed', () => {
  const pick = (seed) => start({ ...poolSheet(0, 0, 12), seed }, 3).ids.slice().sort();
  assert.deepEqual(pick(3), pick(3));
  const seen = new Set();
  for (let seed = 1; seed <= 10; seed++) pick(seed).forEach((id) => seen.add(id));
  assert.ok(seen.size > 3, 'different seeds pick different unseen questions');
});

// ---- Sampler: Subdomain weakness drawing

// Share of 300 seeded one-question tests (all due, two Subdomains 1.1 and 1.2)
// that drew Subdomain 1.1.
function share11(attempts, extraBank = {}, runs = 300) {
  const bank = makeBank({ '1.1': 2, '1.2': 2 }, extraBank);
  const states = ['q_1.1_1', 'q_1.1_2', 'q_1.2_1', 'q_1.2_2'].map((id) => stateRow(id, 1, '2026-11-10', '2026-11-01T08:00:00Z'));
  let hits = 0;
  for (let seed = 1; seed <= runs; seed++) {
    const { ids } = start({ bank, states, attempts, seed, settings: { section_weights: '' } }, 1);
    if (subOf(ids[0]) === '1.1') hits++;
  }
  return hits / runs;
}

const rowsFor = (id, result, n, extra) => Array.from({ length: n }, () => attemptRow(id, result, extra));

test('drawing weights Subdomains by weakness; no attempts scores 0.5', () => {
  // 1.1 all wrong (30): 1 - 2/34 = 0.94. 1.2 none: 0.5. Expected 0.65.
  const p = share11(rowsFor('q_1.1_1', 'wrong', 30));
  assert.ok(p > 0.55 && p < 0.75, String(p));
  // No attempts anywhere: 0.5 each.
  const even = share11([]);
  assert.ok(even > 0.4 && even < 0.6, String(even));
});

test('a strong Subdomain keeps the 0.1 floor', () => {
  // 1.1 all correct (30): 0.059 → floor 0.1. 1.2 all wrong: 0.94. Expected 0.096
  // with the floor, 0.059 without it.
  const p = share11([...rowsFor('q_1.1_1', 'correct', 30), ...rowsFor('q_1.2_1', 'wrong', 30)], {}, 1500);
  assert.ok(p > 0.08 && p < 0.12, String(p));
});

test('weakness uses the last 30 non-skipped attempts of both modes', () => {
  // 1.1: 40 old wrongs, then 30 corrects in mock mode, then 10 skipped. Window → floor 0.1
  // against 0.5 (expected 0.17). Over all 70 graded rows it would be 0.57 (expected 0.53).
  const attempts = [
    ...rowsFor('q_1.1_1', 'wrong', 40),
    ...rowsFor('q_1.1_2', 'correct', 30, { mode: 'mock', test_id: 't_20261101T080000Z', flagged: 'FALSE' }),
    ...rowsFor('q_1.1_2', 'skipped', 10, { mode: 'mock', test_id: 't_20261101T080000Z', flagged: 'FALSE' }),
  ];
  const p = share11(attempts);
  assert.ok(p > 0.08 && p < 0.27, String(p));
});

test('weakness leaves out retired and missing IDs', () => {
  // Wrongs on a retired 1.1 question and a missing ID: 1.1 still scores 0.5.
  const p = share11([...rowsFor('q_1.1_r1', 'wrong', 30), ...rowsFor('q_gone00000000', 'wrong', 30)], { '1.1': 1 });
  assert.ok(p > 0.4 && p < 0.6, String(p));
});

// ---- getMockTest, discard, home card

function itemRow(testId, position, id, selected = '', flagged = 'FALSE') {
  const o = { test_id: testId, position: String(position), question_id: id, choice_order: 'ABCD', selected, flagged, question_updated_at: '2026-11-01T10:00:00Z' };
  return ITEM_HEADERS.map((h) => o[h]);
}

const RUNNING = ['t_20261117T081500Z', 'in_progress', '2026-11-17T08:15:00Z', '', '3', '60', '2712', '', ''];
const SUBMITTED = ['t_20261110T081500Z', 'submitted', '2026-11-10T08:15:00Z', '2026-11-10T09:00:00Z', '3', '60', '100', '2', '66.7'];

function runningSheet() {
  return sheet({
    tests: [SUBMITTED, RUNNING],
    items: [
      itemRow(RUNNING[0], 2, 'q_dba0082ec68e', 'A'), // multi A,C: part answered
      itemRow(RUNNING[0], 1, 'q_042896dc1966', 'B', 'TRUE'),
      itemRow(RUNNING[0], 3, 'q_dfd5922f5aa9', '', 'TRUE'),
    ],
  });
}

test('getMockTest returns the unfinished test for the pause screen', () => {
  const { server } = runningSheet();
  const { test: t } = server.getMockTest();
  assert.equal(t.test_id, RUNNING[0]);
  assert.equal(t.seconds_left, 2712);
  assert.equal(t.question_count, 3);
  assert.equal(t.minutes_allowed, 60);
  assert.equal(t.answered, 1);
  assert.equal(t.flagged, 2);
  assert.equal(t.started_on, '2026-11-17');
  assert.deepEqual(t.items.map((i) => i.position), [1, 2, 3]);
  assert.deepEqual(t.items[0], { position: 1, question_id: 'q_042896dc1966', choice_order: 'ABCD', selected: 'B', flagged: true, question_updated_at: '2026-11-01T10:00:00Z' });
});

test('getMockTest with no unfinished test returns no test', () => {
  assert.deepEqual(sheet({ tests: [SUBMITTED] }).server.getMockTest(), { test: null });
});

test('discard sets discarded, clears MockTestItems and writes no Attempts', () => {
  const { fake, server } = runningSheet();
  assert.deepEqual(server.discardMockTest(), { ok: true });
  const tests = rowsOf(fake, 'MockTests');
  assert.deepEqual(tests.map((r) => r.status), ['submitted', 'discarded']);
  assert.equal(tests[1].seconds_left, '2712');
  assert.deepEqual(fake.values('MockTestItems'), [ITEM_HEADERS]);
  assert.equal(rowsOf(fake, 'Attempts').length, 0);
  assert.deepEqual(server.getMockTest(), { test: null });
  assert.equal(server.discardMockTest().error, 'not_unfinished');
});

test('after a discard a new test can start', () => {
  const s = sheet();
  s.server.startMockTest(4, 10);
  s.server.discardMockTest();
  s.fake.setNow('2026-11-18T08:05:00Z');
  const result = s.server.startMockTest(2, 10);
  assert.equal(result.error, undefined);
  assert.deepEqual(rowsOf(s.fake, 'MockTests').map((r) => r.status), ['discarded', 'in_progress']);
  assert.equal(rowsOf(s.fake, 'MockTestItems').length, 2);
});

test('home carries the unfinished test summary, or null', () => {
  assert.equal(sheet().server.load().mockTest, null);
  const home = runningSheet().server.load();
  assert.equal(home.screen, 'home');
  assert.deepEqual(home.mockTest, { answered: 1, question_count: 3, seconds_left: 2712, started_on: '2026-11-17' });
  assert.equal(home.settings.mock_question_count, '10');
  assert.equal(home.settings.mock_minutes, '120');
});

test('a started test shows on the next load', () => {
  const s = sheet();
  s.server.startMockTest(5, 10);
  assert.deepEqual(s.server.load().mockTest, { answered: 0, question_count: 5, seconds_left: 600, started_on: TODAY });
});

// ---- saveMockTest

function savedSheet() {
  const s = runningSheet();
  return { ...s, items: () => rowsOf(s.fake, 'MockTestItems'), tests: () => rowsOf(s.fake, 'MockTests') };
}

test('a save writes the changed items and the clock, and leaves every other row as it was', () => {
  const { fake, server, items, tests } = savedSheet();
  const before = items();
  const submittedBefore = tests()[0];
  const res = server.saveMockTest([{ position: 2, selected: ['C', 'A'], flagged: false }], 2700);
  assert.deepEqual(res, { ok: true });
  const after = items();
  assert.deepEqual(after.find((r) => r.position === '2'), { ...before.find((r) => r.position === '2'), selected: 'A,C' });
  assert.deepEqual(after.filter((r) => r.position !== '2'), before.filter((r) => r.position !== '2'));
  assert.equal(tests()[1].seconds_left, '2700');
  assert.deepEqual(tests()[0], submittedBefore);
  assert.equal(rowsOf(fake, 'Attempts').length, 0);
});

test('a flag-only change keeps the picks', () => {
  const { server, items } = savedSheet();
  server.saveMockTest([{ position: 1, selected: ['B'], flagged: true }, { position: 2, selected: ['A'], flagged: true }], 2712);
  const byPos = Object.fromEntries(items().map((r) => [r.position, r]));
  assert.equal(byPos['1'].flagged, 'TRUE');
  assert.equal(byPos['1'].selected, 'B');
  assert.equal(byPos['2'].flagged, 'TRUE');
  server.saveMockTest([{ position: 1, selected: ['B'], flagged: false }], 2712);
  assert.equal(items().find((r) => r.position === '1').flagged, 'FALSE');
});

test('a save never raises seconds_left', () => {
  const { server, tests } = savedSheet();
  server.saveMockTest([], 3000);
  assert.equal(tests()[1].seconds_left, '2712');
  server.saveMockTest([], 2000);
  assert.equal(tests()[1].seconds_left, '2000');
  server.saveMockTest([], 2500);
  assert.equal(tests()[1].seconds_left, '2000');
});

test('a clock that is not a number keeps the stored value; a negative clock stores 0', () => {
  const { server, tests } = savedSheet();
  server.saveMockTest([], 'soon');
  assert.equal(tests()[1].seconds_left, '2712');
  server.saveMockTest([], undefined);
  assert.equal(tests()[1].seconds_left, '2712');
  server.saveMockTest([], -5);
  assert.equal(tests()[1].seconds_left, '0');
});

test('empty changes write only the clock', () => {
  const { server, items } = savedSheet();
  const before = items();
  assert.deepEqual(server.saveMockTest([], 2600), { ok: true });
  assert.deepEqual(items(), before);
});

test('a pick can be cleared', () => {
  const { server, items } = savedSheet();
  server.saveMockTest([{ position: 1, selected: [], flagged: true }], 2700);
  assert.equal(items().find((r) => r.position === '1').selected, '');
});

test('a bad change rejects the whole save and writes nothing', () => {
  const { server, items, tests } = savedSheet();
  const itemsBefore = items();
  const testsBefore = tests();
  const bad = [
    [{ position: 9, selected: ['A'], flagged: false }],
    [{ position: 1, selected: ['Z'], flagged: false }],
    [{ position: 1, selected: ['A', 'A'], flagged: false }],
    [{ position: 1, selected: 'A', flagged: false }],
    [{ position: 1, selected: ['A'], flagged: 'yes' }],
    'nope',
  ];
  for (const changes of bad) {
    const res = server.saveMockTest([{ position: 3, selected: ['B'], flagged: true }].concat(changes), 100);
    assert.equal(res.error, 'bad_changes', JSON.stringify(changes));
    assert.deepEqual(items(), itemsBefore);
    assert.deepEqual(tests(), testsBefore);
  }
});

test('a letter outside the item choice_order is refused', () => {
  const row = itemRow(RUNNING[0], 1, 'q_042896dc1966');
  row[ITEM_HEADERS.indexOf('choice_order')] = 'CA';
  const s = sheet({ tests: [RUNNING], items: [row] });
  assert.equal(s.server.saveMockTest([{ position: 1, selected: ['B'], flagged: false }], 100).error, 'bad_changes');
  assert.deepEqual(s.server.saveMockTest([{ position: 1, selected: ['C', 'A'], flagged: false }], 100), { ok: true });
});

test('a save with no unfinished test returns not_unfinished and writes nothing', () => {
  const s = sheet({ tests: [SUBMITTED] });
  const before = s.fake.values('MockTests');
  const res = s.server.saveMockTest([{ position: 1, selected: ['A'], flagged: true }], 10);
  assert.equal(res.error, 'not_unfinished');
  assert.deepEqual(s.fake.values('MockTests'), before);
  assert.deepEqual(s.fake.values('MockTestItems'), [ITEM_HEADERS]);
});

test('a save after discard returns not_unfinished', () => {
  const { server, tests } = savedSheet();
  server.discardMockTest();
  assert.equal(server.saveMockTest([{ position: 1, selected: ['A'], flagged: false }], 10).error, 'not_unfinished');
  assert.equal(tests()[1].seconds_left, '2712');
});

test('a save shows in the next load summary and getMockTest', () => {
  const { server } = savedSheet();
  server.saveMockTest([{ position: 3, selected: ['A'], flagged: false }], 2000);
  assert.equal(server.load().mockTest.seconds_left, 2000);
  const t = server.getMockTest().test;
  assert.equal(t.seconds_left, 2000);
  assert.equal(t.items[2].selected, 'A');
  assert.equal(t.items[2].flagged, false);
});
