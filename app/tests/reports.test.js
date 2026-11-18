const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, setCell, settingsValues } = require('./bank-fixture.js');

const IDS = ['q_042896dc1966', 'q_dba0082ec68e', 'q_dfd5922f5aa9'];
const [Q1, Q2, Q3] = IDS;

const REPORT_HEADERS = ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution'];

// A set-up sheet with the fixture bank and the given Reports rows (objects). Now is 2026-11-18T08:00:00Z.
function sheet({ now = '2026-11-18T08:00:00Z', reports = [], bank = fixtureBank() } = {}) {
  const fake = makeFakeAdapter({ now });
  fake.props.setup_done_at = '2026-11-01T00:00:00Z';
  fake.addTab('Questions', bank);
  fake.addTab('Settings', settingsValues(), { plainText: true, frozenRows: 1 });
  const tabs = {
    QuestionState: ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'],
    Attempts: ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'],
    MockTests: ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'],
    MockTestItems: ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'],
  };
  for (const [name, headers] of Object.entries(tabs)) fake.addTab(name, [headers], { plainText: true, frozenRows: 1 });
  const rows = reports.map((r) => REPORT_HEADERS.map((h) => (r[h] === undefined ? '' : r[h])));
  fake.addTab('Reports', [REPORT_HEADERS, ...rows], { plainText: true, frozenRows: 1 });
  return { fake, server: makeServer(fake.adapter) };
}

function reportsOf(fake) {
  const [headers, ...rows] = fake.values('Reports');
  return rows.map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i]])));
}

function openRow(id, extra = {}) {
  return {
    report_id: 'r_20261110T090000Z', reported_at: '2026-11-10T09:00:00Z', question_id: id, note: 'old note',
    question_updated_at: '2026-11-01T10:00:00Z', status: 'open', ...extra,
  };
}

// A bank with rechecked_at / recheck_note set on sheet row 2 (Q1) and row 3 (Q2).
function bankWithRecheck(rows) {
  const bank = fixtureBank();
  for (const [sheetRow, at, note] of rows) {
    setCell(bank, sheetRow, 'rechecked_at', at);
    setCell(bank, sheetRow, 'recheck_note', note);
  }
  return bank;
}

// ---- saveReport

test('saveReport with no open row creates one: open, ids, bank updated_at', () => {
  const { fake, server } = sheet();

  const row = server.saveReport(Q1, '  The answer should be C.  ');

  assert.equal(row.status, 'open');
  assert.equal(row.note, 'The answer should be C.');
  assert.equal(row.question_id, Q1);
  assert.equal(row.report_id, 'r_20261118T080000Z');
  assert.equal(row.reported_at, '2026-11-18T08:00:00Z');
  assert.match(row.question_updated_at, /^\d{4}-\d{2}-\d{2}T/);
  assert.deepEqual(reportsOf(fake), [row]);
});

test('saveReport on a question with an open row edits it and moves reported_at to now', () => {
  const { fake, server } = sheet({ reports: [openRow(Q1)] });

  const row = server.saveReport(Q1, 'new note');

  const rows = reportsOf(fake);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].note, 'new note');
  assert.equal(rows[0].reported_at, '2026-11-18T08:00:00Z');
  assert.equal(rows[0].report_id, 'r_20261110T090000Z');
  assert.equal(rows[0].status, 'open');
  assert.equal(row.note, 'new note');
});

test('one open row per question: other questions get their own row', () => {
  const { fake, server } = sheet();

  server.saveReport(Q1, 'a');
  server.saveReport(Q1, 'b');
  server.saveReport(Q2, 'c');

  const rows = reportsOf(fake);
  assert.deepEqual(rows.map((r) => [r.question_id, r.note, r.status]), [[Q1, 'b', 'open'], [Q2, 'c', 'open']]);
});

test('after a resolve a new save creates a new row and leaves the resolved one', () => {
  const resolved = openRow(Q1, { status: 'resolved', resolved_at: '2026-11-12T09:00:00Z', resolution: 'Fixed.' });
  const { fake, server } = sheet({ reports: [resolved] });

  server.saveReport(Q1, 'again');

  const rows = reportsOf(fake);
  assert.deepEqual(rows.map((r) => r.status), ['resolved', 'open']);
  assert.equal(rows[0].resolution, 'Fixed.');
  assert.equal(rows[1].note, 'again');
});

test('the note is required and at most 1,000 characters', () => {
  const { fake, server } = sheet();

  assert.equal(server.saveReport(Q1, '').error, 'bad_report');
  assert.equal(server.saveReport(Q1, '   \n ').error, 'bad_report');
  assert.equal(server.saveReport(Q1, undefined).error, 'bad_report');
  assert.equal(server.saveReport(Q1, 'x'.repeat(1001)).error, 'bad_report');
  assert.equal(reportsOf(fake).length, 0);
  assert.equal(server.saveReport(Q1, 'x'.repeat(1000)).status, 'open');
  assert.equal(server.saveReport(Q2, 'x').status, 'open');
});

test('saveReport refuses an ID that is not in the bank', () => {
  const { fake, server } = sheet();

  assert.equal(server.saveReport('q_gone00000000', 'note').error, 'bad_report');
  assert.equal(reportsOf(fake).length, 0);
});

test('saveReport returns the busy error when the lock is held elsewhere', () => {
  const { fake, server } = sheet();
  fake.holdLockElsewhere();

  assert.equal(server.saveReport(Q1, 'note').error, 'busy');
  assert.equal(reportsOf(fake).length, 0);
});

// ---- getReports

test('getReports returns the open row and the last resolved row', () => {
  const { server } = sheet({
    reports: [
      openRow(Q1, { report_id: 'r_1', status: 'resolved', resolved_at: '2026-11-12T09:00:00Z', resolution: 'first' }),
      openRow(Q1, { report_id: 'r_2', status: 'resolved', resolved_at: '2026-11-15T09:00:00Z', resolution: 'second' }),
      openRow(Q1, { report_id: 'r_3', status: 'open', note: 'now' }),
      openRow(Q2, { report_id: 'r_4', status: 'resolved', resolved_at: '2026-11-13T09:00:00Z', resolution: 'other' }),
    ],
  });

  const got = server.getReports(Q1);

  assert.equal(got.open.report_id, 'r_3');
  assert.equal(got.open.note, 'now');
  assert.equal(got.resolved.report_id, 'r_2');
  assert.equal(got.resolved.resolution, 'second');
  assert.deepEqual(server.getReports(Q3), { open: null, resolved: null });
  assert.equal(server.getReports(Q2).open, null);
});

// ---- load step 7

test('load resolves an open row whose rechecked_at is later than reported_at, copying recheck_note', () => {
  const { fake, server } = sheet({
    reports: [openRow(Q1)],
    bank: bankWithRecheck([[2, '2026-11-14T10:00:00Z', 'Answer overturned to C.']]),
  });

  const home = server.load();

  const [row] = reportsOf(fake);
  assert.equal(row.status, 'resolved');
  assert.equal(row.resolved_at, '2026-11-18T08:00:00Z');
  assert.equal(row.resolution, 'Answer overturned to C.');
  assert.equal(row.note, 'old note');
  assert.equal(home.screen, 'home');
  assert.deepEqual(home.openReports, []);
  assert.ok(home.warnings.some((w) => w.id === 'reports_rechecked'
    && w.text === "1 Report was re-checked. Open a question's Report panel to read the result."));
});

test('the home line counts every resolved row and shows once', () => {
  const { server } = sheet({
    reports: [openRow(Q1), openRow(Q2)],
    bank: bankWithRecheck([[2, '2026-11-14T10:00:00Z', 'a'], [3, '2026-11-14T10:00:00Z', 'b']]),
  });

  const first = server.load();
  const second = server.load();

  assert.equal(first.warnings.find((w) => w.id === 'reports_rechecked').text,
    "2 Reports were re-checked. Open a question's Report panel to read the result.");
  assert.equal(second.warnings.some((w) => w.id === 'reports_rechecked'), false);
});

test('an open row stays open when rechecked_at is not later than reported_at, or empty', () => {
  const { fake, server } = sheet({
    reports: [openRow(Q1), openRow(Q2), openRow(Q3)],
    bank: bankWithRecheck([[2, '2026-11-10T09:00:00Z', 'same moment'], [3, '2026-11-09T09:00:00Z', 'before']]),
  });

  const home = server.load();

  assert.deepEqual(reportsOf(fake).map((r) => r.status), ['open', 'open', 'open']);
  assert.equal(home.warnings.some((w) => w.id === 'reports_rechecked'), false);
});

test('a question changed for another reason (updated_at only) stays open', () => {
  const bank = fixtureBank();
  setCell(bank, 2, 'updated_at', '2026-11-17T10:00:00Z');
  const { fake, server } = sheet({ reports: [openRow(Q1)], bank });

  server.load();

  assert.equal(reportsOf(fake)[0].status, 'open');
});

test('a Report whose ID is missing from Questions stays open', () => {
  const { fake, server } = sheet({
    reports: [openRow('q_gone00000000')],
    bank: bankWithRecheck([[2, '2026-11-14T10:00:00Z', 'x']]),
  });

  const home = server.load();

  assert.equal(reportsOf(fake)[0].status, 'open');
  assert.equal(home.warnings.some((w) => w.id === 'reports_rechecked'), false);
});

test('resolved rows are not touched again on a later load', () => {
  const resolved = openRow(Q1, { status: 'resolved', resolved_at: '2026-11-12T09:00:00Z', resolution: 'kept' });
  const { fake, server } = sheet({ reports: [resolved], bank: bankWithRecheck([[2, '2026-11-17T10:00:00Z', 'newer']]) });

  server.load();

  assert.equal(reportsOf(fake)[0].resolution, 'kept');
  assert.equal(reportsOf(fake)[0].resolved_at, '2026-11-12T09:00:00Z');
});

test('after a resolve a new Report is a new row, and a later re-check resolves it', () => {
  const { fake, server } = sheet({
    reports: [openRow(Q1)],
    bank: bankWithRecheck([[2, '2026-11-14T10:00:00Z', 'first check']]),
  });
  server.load();

  server.saveReport(Q1, 'still wrong');

  assert.deepEqual(reportsOf(fake).map((r) => r.status), ['resolved', 'open']);
  // The old re-check predates the new Report, so it does not resolve it.
  server.load();
  assert.deepEqual(reportsOf(fake).map((r) => r.status), ['resolved', 'open']);
});

test('a lock that is busy at step 7 returns the busy error and leaves the row open', () => {
  const { fake, server } = sheet({
    reports: [openRow(Q1)],
    bank: bankWithRecheck([[2, '2026-11-14T10:00:00Z', 'x']]),
  });
  fake.holdLockElsewhere();

  assert.equal(server.load().error, 'busy');
  assert.equal(reportsOf(fake)[0].status, 'open');
});

// ---- home

test('home carries the question IDs with an open Report', () => {
  const { server } = sheet({
    reports: [
      openRow(Q2),
      openRow(Q1, { status: 'resolved', resolved_at: '2026-11-12T09:00:00Z', resolution: 'done' }),
      openRow(Q2, { report_id: 'dup' }),
    ],
  });

  const home = server.load();

  assert.deepEqual(home.openReports, [Q2]);
});
