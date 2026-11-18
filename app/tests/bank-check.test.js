const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { fixtureBank, setCell, settingsValues } = require('./bank-fixture.js');

const SHEET_URL = 'https://docs.google.com/spreadsheets/d/bank/edit';
const LEAD = "Some cells were converted on import. Import again with 'Convert text to numbers, dates, and formulas' unticked.";

function loadWith(bank, extraTabs = {}) {
  const fake = makeFakeAdapter({ spreadsheetUrl: SHEET_URL });
  if (bank) fake.addTab('Questions', bank);
  fake.addTab('Settings', settingsValues());
  for (const [name, values] of Object.entries(extraTabs)) fake.addTab(name, values);
  const result = makeServer(fake.adapter).load();
  return { fake, result };
}

function refusedWith(bank) {
  const { result } = loadWith(bank);
  assert.equal(result.screen, 'refused');
  return result;
}

test('the fixture bank passes and home carries its bank rows', () => {
  const { result } = loadWith(fixtureBank());

  assert.equal(result.screen, 'home');
  assert.equal(result.bank.length, 12);
  assert.equal(result.bank.filter((r) => r.status === 'active').length, 11);
  assert.equal(result.bank.filter((r) => r.status === 'retired').length, 1);
  assert.equal(result.bank[0].id, 'q_042896dc1966');
  assert.equal(result.bank[1].answer, 'A,C');
  assert.deepEqual(result.warnings, []);
});

test('case 1: an empty Questions tab is refused', () => {
  const { result } = loadWith(null); // load creates the tab, empty
  assert.equal(result.screen, 'refused');
  assert.deepEqual(result.messages, ['The Questions tab is empty.']);
});

test('case 1: a header row with no data row is refused', () => {
  const bank = fixtureBank().slice(0, 1);
  assert.deepEqual(refusedWith(bank).messages, ['The Questions tab is empty.']);
});

test('case 2: each missing header is named', () => {
  const bank = fixtureBank().map((r, i) => r.filter((_, c) => ![1, 4].includes(c))); // exam, subdomain_title
  assert.deepEqual(refusedWith(bank).messages, ['Missing column: `exam`', 'Missing column: `subdomain_title`']);
});

test('case 3: an empty id names its row', () => {
  const bank = setCell(fixtureBank(), 4, 'id', '');
  assert.deepEqual(refusedWith(bank).messages, ['Row 4: empty id']);
});

test('case 4: a duplicate id names both rows', () => {
  const bank = setCell(fixtureBank(), 5, 'id', 'q_042896dc1966');
  assert.deepEqual(refusedWith(bank).messages, ['Row 5: duplicate id `q_042896dc1966`, first seen in row 2']);
});

test('case 5: a number in subdomain refuses and leads with the Convert text line', () => {
  const bank = setCell(fixtureBank(), 9, 'subdomain', 2.1);
  const result = refusedWith(bank);
  assert.deepEqual(result.messages, ['Row 9: `subdomain` is not text']);
  assert.equal(result.lead, LEAD);
});

test('case 5: id, answer, uncertain and updated_at cells that are not text', () => {
  let bank = setCell(fixtureBank(), 2, 'id', 42);
  bank = setCell(bank, 3, 'answer', true);
  bank = setCell(bank, 4, 'uncertain', false);
  bank = setCell(bank, 5, 'updated_at', new Date('2026-11-01T10:00:00Z'));
  const result = refusedWith(bank);
  assert.deepEqual(result.messages, [
    'Row 2: `id` is not text',
    'Row 3: `answer` is not text',
    'Row 4: `uncertain` is not text',
    'Row 5: `updated_at` is not text',
  ]);
  assert.equal(result.lead, LEAD);
});

test('case 5: an empty cell is not a failure, and other cases have no lead line', () => {
  const bank = setCell(fixtureBank(), 13, 'answer', ''); // retired row may have no answer
  assert.equal(loadWith(bank).result.screen, 'home');
  const refused = refusedWith(setCell(fixtureBank(), 3, 'status', 'draft'));
  assert.equal(refused.lead, '');
});

test('case 6: a status that is not active or retired', () => {
  const bank = setCell(fixtureBank(), 3, 'status', 'draft');
  assert.deepEqual(refusedWith(bank).messages, ['Row 3: status `draft`']);
});

test('case 7: an answer letter pointing at an empty choice, on an active row', () => {
  const bank = setCell(fixtureBank(), 4, 'answer', 'D'); // row 4 has choices a to c only
  assert.deepEqual(refusedWith(bank).messages, ['Row 4: answer `D` has no choice']);
});

test('case 7: a multi-letter answer names the letter that has no choice', () => {
  const bank = setCell(fixtureBank(), 2, 'answer', 'B,F');
  assert.deepEqual(refusedWith(bank).messages, ['Row 2: answer `F` has no choice']);
});

test('case 7 skips retired rows', () => {
  const bank = setCell(fixtureBank(), 13, 'answer', 'F'); // row 13 is the retired question
  assert.equal(loadWith(bank).result.screen, 'home');
});

test('case 8: no active rows', () => {
  const bank = fixtureBank();
  for (let r = 2; r <= 13; r++) setCell(bank, r, 'status', 'retired');
  assert.deepEqual(refusedWith(bank).messages, ['No active questions.']);
});

test('the refusal lists the first 20 messages, then the rest as a count', () => {
  const bank = fixtureBank();
  for (let r = 2; r <= 13; r++) setCell(bank, r, 'status', 'draft');
  for (let r = 2; r <= 13; r++) setCell(bank, r, 'subdomain', 1.5);
  // 24 row messages and "No active questions." = 25
  const result = refusedWith(bank);
  assert.equal(result.messages.length, 20);
  assert.equal(result.more, 5);
  assert.equal(result.messages[0], 'Row 2: `subdomain` is not text');
});

test('a refusal carries the import steps and the spreadsheet link', () => {
  const result = refusedWith(null);
  const template = fs.readFileSync(path.join(__dirname, '..', '..', '.claude', 'skills', 'exam-bank', 'templates', 'import-steps.txt'), 'utf8');
  assert.equal(result.importSteps, template.replace(/\r\n/g, '\n').trim());
  assert.equal(result.spreadsheetUrl, SHEET_URL);
});

test('headers in any order pass', () => {
  const bank = fixtureBank();
  const order = bank[0].map((_, i) => i).reverse();
  const reordered = bank.map((r) => order.map((i) => r[i]));
  const { result } = loadWith(reordered);
  assert.equal(result.screen, 'home');
  assert.equal(result.bank[0].id, 'q_042896dc1966');
  assert.equal(result.bank[0].answer, 'B');
});

test('an extra column warns and is not carried', () => {
  const bank = fixtureBank().map((r, i) => r.concat(i === 0 ? ['my_notes', 'my_tag'] : ['x', 'y']));
  const { result } = loadWith(bank);
  assert.equal(result.screen, 'home');
  assert.deepEqual(result.warnings, [{ id: 'unknown_columns', text: 'The bank has 2 unknown columns. The app ignores them.' }]);
  assert.equal('my_notes' in result.bank[0], false);
});

test('orphan ids warn once per distinct id, across the four tabs, and retired ids are not orphans', () => {
  const { result } = loadWith(fixtureBank(), {
    QuestionState: [['question_id'], ['q_gone1'], ['q_042896dc1966']],
    Attempts: [['question_id'], ['q_gone1'], ['q_gone2'], ['q_b6b3be77081f']],
    Reports: [['question_id'], ['q_gone2']],
    MockTestItems: [['question_id'], ['q_gone3'], ['']],
  });
  assert.deepEqual(result.warnings, [{ id: 'orphans', text: '3 questions with study history are no longer in the bank. Their history is kept.' }]);
  assert.equal(result.bankLine.orphaned, 3);
});

test('the bank line counts active, retired, orphaned and the newest updated_at as a date', () => {
  const bank = setCell(fixtureBank(), 6, 'updated_at', '2026-11-12T23:30:00Z');
  const { result } = loadWith(bank);
  assert.deepEqual(result.bankLine, { active: 11, retired: 1, orphaned: 0, updated: '2026-11-12' });
});

test('the bank line date uses the spreadsheet time zone', () => {
  const fake = makeFakeAdapter({ timeZone: 'Asia/Tokyo' });
  fake.addTab('Settings', settingsValues());
  fake.addTab('Questions', setCell(fixtureBank(), 6, 'updated_at', '2026-11-12T23:30:00Z'));
  assert.equal(makeServer(fake.adapter).load().bankLine.updated, '2026-11-13');
});

test('home carries the import steps and the spreadsheet link for the import panel', () => {
  const { result } = loadWith(fixtureBank());
  assert.ok(result.importSteps.startsWith('Import into the sheet:'));
  assert.equal(result.spreadsheetUrl, SHEET_URL);
});

test('load writes nothing to Questions, refused or not', () => {
  const damaged = setCell(fixtureBank(), 3, 'status', 'draft');
  const { fake } = loadWith(damaged);
  assert.deepEqual(fake.values('Questions'), damaged);
  assert.deepEqual(fake.tabInfo('Questions'), { plainText: false, frozenRows: 0 });
});
