const test = require('node:test');
const assert = require('node:assert/strict');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, setCell, settingsValues } = require('./bank-fixture.js');

const FIELDS = ['exam_name', 'exam_date', 'mock_question_count', 'mock_minutes', 'section_weights'];

function sheet(options = {}, settings = settingsValues()) {
  const fake = makeFakeAdapter({ now: '2026-11-18T08:00:00Z', ...options });
  fake.addTab('Questions', fixtureBank());
  if (settings) fake.addTab('Settings', settings);
  return { fake, server: makeServer(fake.adapter) };
}

function valid(overrides = {}) {
  return {
    exam_name: 'PMLE', exam_date: '2026-12-31', mock_question_count: '10', mock_minutes: '90',
    section_weights: '1:40,2:40,3:20', ...overrides,
  };
}

function settingOf(fake, key) {
  const row = fake.values('Settings').find((r) => r[0] === key);
  return row ? row[1] : undefined;
}

// ---- layout version stop (load step 3)

test('a filled schema_version other than 1 stops with the spec text', () => {
  const { server } = sheet({}, settingsValues({ schema_version: '2' }));
  const result = server.load();
  assert.equal(result.screen, 'version');
  assert.equal(result.message, 'This sheet was set up by a different version of the app (layout 2). Update the app code, see the README, Upkeep.');
});

test('the version stop comes before the bank check', () => {
  const { fake, server } = sheet({}, settingsValues({ schema_version: '7' }));
  fake.removeTab('Questions');
  fake.addTab('Questions', []);
  assert.equal(server.load().screen, 'version');
});

test('an empty schema_version is written as 1', () => {
  const { fake, server } = sheet({}, settingsValues({ schema_version: '' }));
  assert.equal(server.load().screen, 'home');
  assert.equal(settingOf(fake, 'schema_version'), '1');
});

test('a missing schema_version row is added as 1', () => {
  const { fake, server } = sheet({}, settingsValues({ schema_version: null }));
  assert.equal(server.load().screen, 'home');
  assert.equal(settingOf(fake, 'schema_version'), '1');
});

// ---- first open and setup mode

test('first open on a good bank returns the settings screen in setup mode with the defaults', () => {
  const { fake, server } = sheet({}, null);
  const result = server.load();
  assert.equal(result.screen, 'settings');
  assert.equal(result.mode, 'setup');
  assert.deepEqual(result.errors, {});
  assert.deepEqual(result.values, {
    exam_name: '', exam_date: '', mock_question_count: '50', mock_minutes: '120', section_weights: '',
  });
  assert.match(result.hints.section_weights, /Paste the `section_weights` line/);
  assert.equal(settingOf(fake, 'schema_version'), '1');
});

test('saving valid values from setup writes all five rows and returns home with the header', () => {
  const { fake, server } = sheet({}, null);
  assert.equal(server.load().screen, 'settings');
  const result = server.saveSettings(valid());
  assert.equal(result.screen, 'home');
  for (const key of FIELDS) assert.equal(settingOf(fake, key), valid()[key], key);
  assert.equal(settingOf(fake, 'schema_version'), '1');
  assert.equal(fake.values('Settings').length, 7, 'header + six rows');
});

test('saving over existing rows updates them in place and keeps other rows', () => {
  const settings = settingsValues();
  settings.push(['my_extra', 'keep']);
  const { fake, server } = sheet({}, settings);
  server.saveSettings(valid({ exam_name: 'Renamed' }));
  assert.equal(settingOf(fake, 'exam_name'), 'Renamed');
  assert.equal(settingOf(fake, 'my_extra'), 'keep');
  assert.equal(fake.values('Settings').filter((r) => r[0] === 'exam_name').length, 1);
});

test('save is refused with the busy error when the lock is not free', () => {
  const { fake, server } = sheet();
  fake.holdLockElsewhere();
  assert.deepEqual(server.saveSettings(valid()), { error: 'busy', message: 'The sheet is busy. Try again.' });
});

test('a failed save writes nothing', () => {
  const { fake, server } = sheet();
  const before = fake.values('Settings');
  const result = server.saveSettings(valid({ mock_minutes: '0' }));
  assert.ok(result.fieldErrors.mock_minutes);
  assert.deepEqual(fake.values('Settings'), before);
});

// ---- field rules, through saveSettings

function errorsOf(values) {
  const { server } = sheet();
  return server.saveSettings(valid(values)).fieldErrors || {};
}

test('exam_name: non-empty, at most 100 characters', () => {
  assert.ok(errorsOf({ exam_name: '' }).exam_name);
  assert.ok(errorsOf({ exam_name: '   ' }).exam_name);
  assert.ok(errorsOf({ exam_name: 'x'.repeat(101) }).exam_name);
  assert.equal(errorsOf({ exam_name: 'x'.repeat(100) }).exam_name, undefined);
});

test('exam_date: a real YYYY-MM-DD date, a past date allowed', () => {
  for (const bad of ['', '2026-13-01', '2026-02-30', '31/12/2026', '2026-1-5', 'soon']) {
    assert.ok(errorsOf({ exam_date: bad }).exam_date, 'rejects ' + bad);
  }
  assert.equal(errorsOf({ exam_date: '2020-01-01' }).exam_date, undefined, 'past date');
  assert.equal(errorsOf({ exam_date: '2028-02-29' }).exam_date, undefined, 'leap day');
});

test('mock_question_count: integer 1 to 200, above the active rows allowed', () => {
  for (const bad of ['', '0', '201', '2.5', '-3', 'ten', '1e2']) {
    assert.ok(errorsOf({ mock_question_count: bad }).mock_question_count, 'rejects ' + bad);
  }
  assert.equal(errorsOf({ mock_question_count: '1' }).mock_question_count, undefined);
  assert.equal(errorsOf({ mock_question_count: '200' }).mock_question_count, undefined);
});

test('mock_minutes: integer 1 to 600', () => {
  for (const bad of ['', '0', '601', '1.5', 'x']) {
    assert.ok(errorsOf({ mock_minutes: bad }).mock_minutes, 'rejects ' + bad);
  }
  assert.equal(errorsOf({ mock_minutes: '600' }).mock_minutes, undefined);
});

test('every bad field is reported at once', () => {
  const errors = errorsOf({ exam_name: '', exam_date: 'x', mock_question_count: '0', mock_minutes: '0', section_weights: 'zzz' });
  assert.deepEqual(Object.keys(errors).sort(), FIELDS.slice().sort());
});

// ---- section_weights rules (fixture: sections 1, 2, 3 all with active rows)

function weightErr(value) {
  return errorsOf({ section_weights: value }).section_weights;
}

test('section_weights: empty is allowed', () => {
  assert.equal(weightErr(''), undefined);
});

test('section_weights: weights summing to 101 pass', () => {
  assert.equal(weightErr('1:13,2:44,3:44'), undefined);
  assert.equal(weightErr('1:50,2:50,3:1'), undefined);
});

test('section_weights: decimals pass, no sum rule', () => {
  assert.equal(weightErr('1:0.5,2:0.25,3:7'), undefined);
  assert.equal(weightErr('1:1,2:1,3:1'), undefined);
});

test('section_weights: malformed pairs fail', () => {
  for (const bad of ['1:40,2:40,3', '1-40,2:40,3:20', '1:40,,3:20', 'a:1,2:1,3:1', '1:x,2:1,3:1', '1:-5,2:1,3:1', '1:40,2:40,3:20,']) {
    assert.ok(weightErr(bad), 'rejects ' + bad);
  }
});

test('section_weights: an n not found on a Questions row fails', () => {
  assert.match(weightErr('1:1,2:1,3:1,9:5'), /9/);
});

test('section_weights: a repeated n fails', () => {
  assert.match(weightErr('1:1,1:2,2:1,3:1'), /twice|more than once|repeat/i);
});

test('section_weights: a Section with active rows must be present', () => {
  assert.match(weightErr('1:1,2:1'), /3/);
});

test('section_weights: a Section with only retired rows need not be present', () => {
  const bank = fixtureBank();
  // rows of Section 3 are 3.1 active, 3.2 active, 3.2 retired; retire the active ones.
  bank.forEach((r, i) => { if (i > 0 && r[3].startsWith('3.')) setCell(bank, i + 1, 'status', 'retired'); });
  const fake = makeFakeAdapter();
  fake.addTab('Questions', bank);
  fake.addTab('Settings', settingsValues());
  const server = makeServer(fake.adapter);
  assert.equal(server.saveSettings(valid({ section_weights: '1:1,2:1' })).fieldErrors, undefined);
  assert.equal(server.saveSettings(valid({ section_weights: '1:1,2:1,3:1' })).fieldErrors, undefined, 'retired-only Section may be listed');
});

test('section_weights: a weight of 0 is fine, all zero is not', () => {
  assert.equal(weightErr('1:0,2:1,3:1'), undefined);
  assert.ok(weightErr('1:0,2:0,3:0'));
});

test('section_weights: a leading "section_weights:" prefix is stripped on save', () => {
  const { fake, server } = sheet();
  const result = server.saveSettings(valid({ section_weights: '  section_weights: 1:13,2:44,3:44  ' }));
  assert.equal(result.screen, 'home');
  assert.equal(settingOf(fake, 'section_weights'), '1:13,2:44,3:44');
});

test('section_weights: pairs may carry spaces and are stored trimmed', () => {
  const { fake, server } = sheet();
  server.saveSettings(valid({ section_weights: '1:13, 2:44 , 3:44' }));
  assert.equal(settingOf(fake, 'section_weights'), '1:13,2:44,3:44');
});

test('section_weights: the prefix is not stripped on load, so a hand edit with it fails', () => {
  const { server } = sheet({}, settingsValues({ section_weights: 'section_weights:1:13,2:44,3:44' }));
  const result = server.load();
  assert.equal(result.screen, 'settings');
  assert.ok(result.errors.section_weights);
});

// ---- hand edits found on load (step 5)

test('a hand-broken mock_minutes reopens settings with that field marked and its rule shown', () => {
  const { server } = sheet({}, settingsValues({ mock_minutes: '9999' }));
  const result = server.load();
  assert.equal(result.screen, 'settings');
  assert.equal(result.mode, 'fix');
  assert.deepEqual(Object.keys(result.errors), ['mock_minutes']);
  assert.match(result.errors.mock_minutes, /1 to 600/);
  assert.equal(result.values.mock_minutes, '9999', 'the bad value is shown for editing');
});

test('a missing row is a bad value', () => {
  const { server } = sheet({}, settingsValues({ exam_date: null }));
  const result = server.load();
  assert.equal(result.screen, 'settings');
  assert.equal(result.mode, 'fix');
  assert.ok(result.errors.exam_date);
});

test('a hand-typed number cell is read as its text', () => {
  const { server } = sheet({}, settingsValues({ mock_minutes: 90, schema_version: 1 }));
  assert.equal(server.load().screen, 'home');
});

test('a refused bank wins over bad settings', () => {
  const { fake, server } = sheet({}, settingsValues({ mock_minutes: '0' }));
  fake.removeTab('Questions');
  fake.addTab('Questions', []);
  assert.equal(server.load().screen, 'refused');
});

test('settings from a section_weights edit that no longer matches the bank reopen the screen', () => {
  const { server } = sheet({}, settingsValues({ section_weights: '1:1,2:1' }));
  const result = server.load();
  assert.equal(result.screen, 'settings');
  assert.ok(result.errors.section_weights);
});

// ---- home header and dates

function headerFor(examDate, now = '2026-11-18T08:00:00Z', options = {}) {
  const { server } = sheet({ now, ...options }, settingsValues({ exam_date: examDate }));
  const result = server.load();
  assert.equal(result.screen, 'home');
  return result.header;
}

test('home header shows the name, the date and N days left', () => {
  assert.deepEqual(headerFor('2026-12-31'), {
    examName: 'Professional ML Engineer', examDate: '2026-12-31', daysLeft: '43 days left',
  });
});

test('home header: one day left', () => {
  assert.equal(headerFor('2026-11-19').daysLeft, '1 day left');
});

test('home header: the day itself reads Exam is today', () => {
  assert.equal(headerFor('2026-11-18').daysLeft, 'Exam is today');
});

test('home header: after the date reads Exam date passed', () => {
  assert.equal(headerFor('2026-11-17').daysLeft, 'Exam date passed · update in Settings');
});

test('days left counts from today in the spreadsheet time zone', () => {
  // 23:30 UTC on the 18th is already the 19th in Tokyo.
  const header = headerFor('2026-11-19', '2026-11-18T23:30:00Z', { timeZone: 'Asia/Tokyo' });
  assert.equal(header.daysLeft, 'Exam is today');
});

test('days left across a month and leap-year boundary', () => {
  assert.equal(headerFor('2028-03-01', '2028-02-28T12:00:00Z').daysLeft, '2 days left');
});

test('every date crosses to the client as a string', () => {
  const { server } = sheet({}, settingsValues());
  const result = server.load();
  assert.equal(typeof result.today, 'string');
  assert.equal(typeof result.header.examDate, 'string');
  assert.equal(typeof result.settings.exam_date, 'string');
  JSON.stringify(result);
});

test('home carries the weights hint for the Settings link', () => {
  const { server } = sheet();
  assert.match(server.load().hints.section_weights, /Leave empty to follow the bank's own mix\.$/);
});

test('home carries the five settings values for the Settings link', () => {
  const { server } = sheet();
  assert.deepEqual(server.load().settings, {
    exam_name: 'Professional ML Engineer', exam_date: '2026-12-31', mock_question_count: '10',
    mock_minutes: '120', section_weights: '1:40,2:40,3:20',
  });
});

// ---- the fewer-active-rows banner

test('home warns when the bank has fewer active rows than mock_question_count', () => {
  const { server } = sheet({}, settingsValues({ mock_question_count: '50' }));
  const warnings = server.load().warnings;
  assert.deepEqual(warnings, [{ id: 'few_active', text: 'The bank has 11 active questions. A Mock Test of 50 will be shorter.' }]);
});

test('no banner when the count equals the active rows', () => {
  const { server } = sheet({}, settingsValues({ mock_question_count: '11' }));
  assert.deepEqual(server.load().warnings, []);
});
