// Test helpers: the fixture bank as sheet values, and small edits of it.
const fs = require('node:fs');
const path = require('node:path');

// Minimal RFC 4180 reader: quoted cells, doubled quotes, newlines inside quotes.
function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); cell = '';
      rows.push(row); row = [];
    } else cell += ch;
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

// Header row first, then one array per question. Fresh copy on every call.
function fixtureBank() {
  const file = path.join(__dirname, 'fixtures', 'fixture-bank.csv');
  return parseCsv(fs.readFileSync(file, 'utf8'));
}

// Sets one cell of a bank (values array) by sheet row number (header = 1).
function setCell(bank, sheetRow, column, value) {
  bank[sheetRow - 1][bank[0].indexOf(column)] = value;
  return bank;
}

// A valid Settings tab (header + five rows + schema_version). `overrides` replaces
// a value by key; a value of null drops the row.
function settingsValues(overrides = {}) {
  const base = {
    exam_name: 'Professional ML Engineer',
    exam_date: '2026-12-31',
    mock_question_count: '10',
    mock_minutes: '120',
    section_weights: '1:40,2:40,3:20',
    schema_version: '1',
  };
  const merged = { ...base, ...overrides };
  const rows = Object.keys(merged).filter((k) => merged[k] !== null).map((k) => [k, merged[k]]);
  return [['key', 'value'], ...rows];
}

module.exports = { parseCsv, fixtureBank, setCell, settingsValues };
