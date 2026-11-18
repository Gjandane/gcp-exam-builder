// The Demo bank (docs/demo/demo-bank.csv) passes the Bank check. Spec 0002, Demo bank.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { makeServer } = require('./load-server.js');
const { makeFakeAdapter } = require('./fake-adapter.js');
const { parseCsv, settingsValues } = require('./bank-fixture.js');

const DEMO = path.join(__dirname, '..', '..', 'docs', 'demo', 'demo-bank.csv');

function demoBank() {
  return parseCsv(fs.readFileSync(DEMO, 'utf8'));
}

test('the Demo bank passes the Bank check with its section_weights line', () => {
  const fake = makeFakeAdapter({ spreadsheetUrl: 'https://docs.google.com/spreadsheets/d/demo/edit' });
  fake.addTab('Questions', demoBank());
  fake.addTab('Settings', settingsValues({
    exam_name: 'PMLE (demo)',
    section_weights: '1:13,2:16,3:21,4:20,5:18,6:13',
  }));
  const result = makeServer(fake.adapter).load();

  assert.equal(result.screen, 'home');
  assert.equal(result.bank.length, 25);
  assert.ok(result.bank.every((r) => r.status === 'active'));
  assert.deepEqual(result.warnings, []);
});

test('the Demo bank is all created, covers 5+ Subdomains, and has 1 or 2 Uncertain answers', () => {
  const [header, ...rows] = demoBank();
  const col = (name) => header.indexOf(name);
  assert.ok(rows.every((r) => r[col('lineage')] === 'created'));
  assert.ok(new Set(rows.map((r) => r[col('subdomain')])).size >= 5);
  const uncertain = rows.filter((r) => r[col('uncertain')] === 'TRUE').length;
  assert.ok(uncertain >= 1 && uncertain <= 2);
});
