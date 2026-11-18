const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, settingsValues } = require('./bank-fixture.js');

// Header rows copied from spec 0002, Sheet tabs.
const APP_TAB_HEADERS = {
  Settings: ['key', 'value'],
  QuestionState: ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'],
  Attempts: ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'],
  MockTests: ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'],
  MockTestItems: ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'],
  Reports: ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution'],
};
const SEVEN_TABS = ['Questions', ...Object.keys(APP_TAB_HEADERS)];

test('first open creates the seven tabs and sets the mark', () => {
  const fake = makeFakeAdapter({ now: '2026-11-18T08:15:00Z' });
  fake.addTab('Sheet1');

  const result = makeServer(fake.adapter).load();

  assert.equal(result.screen, 'refused', 'the empty Questions tab is refused with the import steps');
  for (const name of SEVEN_TABS) assert.ok(fake.tabNames().includes(name), name + ' created');
  for (const [name, headers] of Object.entries(APP_TAB_HEADERS)) {
    const body = name === 'Settings' ? [['schema_version', '1']] : [];
    assert.deepEqual(fake.values(name), [headers, ...body], name + ' holds its header row' + (body.length ? ' and schema_version' : ' only'));
    assert.deepEqual(fake.tabInfo(name), { plainText: true, frozenRows: 1 }, name + ' is plain text with row 1 frozen');
  }
  assert.deepEqual(fake.values('Questions'), [], 'Questions is created empty');
  assert.equal(fake.props.setup_done_at, '2026-11-18T08:15:00Z');
  assert.ok(fake.tabNames().includes('Sheet1'), 'other tabs are left alone');
});

test('mark present with Attempts missing returns wipe and creates nothing', () => {
  const fake = makeFakeAdapter({ spreadsheetUrl: 'https://docs.google.com/spreadsheets/d/abc/edit' });
  fake.props.setup_done_at = '2026-11-01T09:00:00Z';
  fake.addTab('Questions', [['id'], ['q_1']]);
  fake.addTab('Settings', [APP_TAB_HEADERS.Settings]);

  const result = makeServer(fake.adapter).load();

  assert.deepEqual(result, { screen: 'wipe', spreadsheetUrl: 'https://docs.google.com/spreadsheets/d/abc/edit' });
  assert.deepEqual(fake.tabNames(), ['Questions', 'Settings']);
  assert.deepEqual(fake.values('Questions'), [['id'], ['q_1']]);
  assert.equal(fake.props.setup_done_at, '2026-11-01T09:00:00Z');
});

test('the wipe guard creates nothing even when no tab is left', () => {
  const fake = makeFakeAdapter();
  fake.props.setup_done_at = '2026-11-01T09:00:00Z';
  fake.addTab('replace-test');

  assert.equal(makeServer(fake.adapter).load().screen, 'wipe');
  assert.deepEqual(fake.tabNames(), ['replace-test']);
});

test('a copied sheet sets the mark and creates only the missing tabs', () => {
  const fake = makeFakeAdapter({ now: '2026-11-18T10:00:00Z' });
  const attempts = [APP_TAB_HEADERS.Attempts, ['2026-11-10T08:00:00Z', 'q_1', 'review', '', 'B', 'B', 'correct', '2026-11-01T10:00:00Z', '']];
  fake.addTab('Questions', fixtureBank());
  fake.addTab('Attempts', attempts);
  fake.addTab('Settings', settingsValues({ exam_name: 'PMLE' }));

  const result = makeServer(fake.adapter).load();

  assert.equal(result.screen, 'home');
  assert.equal(fake.props.setup_done_at, '2026-11-18T10:00:00Z');
  for (const name of SEVEN_TABS) assert.ok(fake.tabNames().includes(name), name + ' present');
  assert.deepEqual(fake.values('Attempts'), attempts, 'existing rows are kept');
  assert.deepEqual(fake.values('Settings'), settingsValues({ exam_name: 'PMLE' }));
  assert.deepEqual(fake.values('Reports'), [APP_TAB_HEADERS.Reports]);
});

test('a normal sheet recreates a missing tab and keeps the mark', () => {
  const fake = makeFakeAdapter({ now: '2026-11-18T10:00:00Z' });
  fake.props.setup_done_at = '2026-11-01T09:00:00Z';
  for (const [name, headers] of Object.entries(APP_TAB_HEADERS)) {
    if (name !== 'Reports' && name !== 'Settings') fake.addTab(name, [headers]);
  }
  fake.addTab('Settings', settingsValues());
  fake.addTab('Questions', fixtureBank());

  const result = makeServer(fake.adapter).load();

  assert.equal(result.screen, 'home');
  assert.deepEqual(fake.values('Reports'), [APP_TAB_HEADERS.Reports]);
  assert.equal(fake.props.setup_done_at, '2026-11-01T09:00:00Z');
});

test('load never writes to an existing Questions tab', () => {
  const fake = makeFakeAdapter();
  const bank = [['id', 'subdomain', 'answer'], ['q_1', '2.10', 'A,C'], ['q_2', '1.1', 'B']];
  fake.addTab('Questions', bank);

  makeServer(fake.adapter).load();
  makeServer(fake.adapter).load();

  assert.deepEqual(fake.values('Questions'), bank);
  assert.deepEqual(fake.tabInfo('Questions'), { plainText: false, frozenRows: 0 });
});

test('home carries today in the spreadsheet time zone', () => {
  const fake = makeFakeAdapter({ now: '2026-11-18T23:30:00Z', timeZone: 'Asia/Tokyo' });
  fake.addTab('Questions', fixtureBank());
  fake.addTab('Settings', settingsValues());

  const result = makeServer(fake.adapter).load();

  assert.equal(result.screen, 'home');
  assert.equal(result.today, '2026-11-19');
});

test('tab creation waits for the script lock and reports a busy sheet', () => {
  const fake = makeFakeAdapter();
  fake.addTab('Sheet1');
  fake.holdLockElsewhere();

  const result = makeServer(fake.adapter).load();

  assert.deepEqual(result, { error: 'busy', message: 'The sheet is busy. Try again.' });
  assert.deepEqual(fake.tabNames(), ['Sheet1']);
  assert.equal(fake.props.setup_done_at, undefined);
});

test('a later load recreates a tab deleted after setup', () => {
  const fake = makeFakeAdapter();
  fake.addTab('Questions', fixtureBank());
  fake.addTab('Settings', settingsValues());
  makeServer(fake.adapter).load();
  fake.removeTab('MockTests');

  assert.equal(makeServer(fake.adapter).load().screen, 'home');
  assert.deepEqual(fake.values('MockTests'), [APP_TAB_HEADERS.MockTests]);
});
