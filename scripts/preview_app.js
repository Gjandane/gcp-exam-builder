// Local preview of the study app, for README captures. Spec 0002, Visuals, app side.
// Serves app/client/index.html with its includes inlined and a stub google.script.run
// that posts each call to /rpc/<fn>. The calls run makeServer over one in-memory fake
// adapter seeded with the Demo bank. No Google deployment, no personal data.
//
//   node scripts/preview_app.js          then open http://localhost:8787
//   PORT=9000 node scripts/preview_app.js
//   PREVIEW_CLOCK_CONTROL=1 adds POST /dev/advance?days=N (capture script only)
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const APP = path.join(ROOT, 'app');
const { makeServer } = require(path.join(APP, 'tests', 'load-server.js'));
const { makeFakeAdapter } = require(path.join(APP, 'tests', 'fake-adapter.js'));
const { parseCsv } = require(path.join(APP, 'tests', 'bank-fixture.js'));

const DEMO_BANK = path.join(ROOT, 'docs', 'demo', 'demo-bank.csv');
const START = Date.parse('2026-11-18T09:00:00Z'); // fixed start; the clock then follows real time
const SETTINGS = [
  ['key', 'value'],
  ['exam_name', 'PMLE (demo)'],
  ['exam_date', '2027-01-15'],
  ['mock_question_count', '10'],
  ['mock_minutes', '30'],
  ['section_weights', '1:13,2:16,3:21,4:20,5:18,6:13'],
  ['schema_version', '1'],
];
// The server interface the client may call: main.js wrappers, without the menu items.
const CALLS = new Set(['load', 'saveSettings', 'getReviewList', 'answerReview', 'setBookmark',
  'saveNote', 'saveReport', 'getReports', 'startMockTest', 'getMockTest', 'saveMockTest',
  'discardMockTest', 'submitMockTest', 'getResults', 'getHistory']);

const STUB = `<script>
(function () {
  function runner(ok, fail) {
    return new Proxy({}, { get: function (_, name) {
      if (name === 'withSuccessHandler') return function (h) { return runner(h, fail); };
      if (name === 'withFailureHandler') return function (h) { return runner(ok, h); };
      if (name === 'withUserObject') return function () { return runner(ok, fail); };
      return function () {
        var args = Array.prototype.slice.call(arguments);
        fetch('/rpc/' + name, { method: 'POST', body: JSON.stringify(args) })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d.ok) { if (ok) ok(d.value); } else if (fail) fail(new Error(d.error));
          });
      };
    } });
  }
  window.google = { script: { run: runner(null, null) } };
})();
</script>`;

function renderIndex() {
  const index = fs.readFileSync(path.join(APP, 'client', 'index.html'), 'utf8');
  const inlined = index.replace(/<\?!=\s*include_\('([^']+)'\);\s*\?>/g,
    (_, name) => fs.readFileSync(path.join(APP, name + '.html'), 'utf8'));
  return inlined.replace('<head>', '<head>\n' + STUB);
}

function makeBackend() {
  const fake = makeFakeAdapter({
    now: new Date(START).toISOString(),
    spreadsheetUrl: 'https://docs.google.com/spreadsheets/d/demo/edit',
    webAppUrl: 'https://script.google.com/macros/s/demo/exec',
  });
  fake.addTab('Questions', parseCsv(fs.readFileSync(DEMO_BANK, 'utf8')), { plainText: true, frozenRows: 1 });
  fake.addTab('Settings', SETTINGS);
  const booted = Date.now();
  let shiftMs = 0;
  function call(fn, args) {
    fake.setNow(new Date(START + shiftMs + (Date.now() - booted)).toISOString());
    return makeServer(fake.adapter)[fn](...args);
  }
  call.advanceDays = (days) => { shiftMs += days * 86400000; };
  return call;
}

// clockControl adds POST /dev/advance?days=N, so the capture script can spread
// Mock Tests over several days for the history chart.
function startPreview({ port = 8787, clockControl = false } = {}) {
  const call = makeBackend();
  const page = renderIndex();
  const server = http.createServer((req, res) => {
    if (req.method === 'GET' && (req.url === '/' || req.url.startsWith('/?'))) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end(page);
    }
    const adv = clockControl && req.method === 'POST' && req.url.match(/^\/dev\/advance\?days=(\d+)$/);
    if (adv) { call.advanceDays(Number(adv[1])); res.writeHead(204); return res.end(); }
    const m = req.method === 'POST' && req.url.match(/^\/rpc\/(\w+)$/);
    if (!m || !CALLS.has(m[1])) { res.writeHead(404); return res.end('Not found'); }
    let body = '';
    req.on('data', (c) => { body += c; });
    req.on('end', () => {
      let reply;
      try {
        const value = call(m[1], JSON.parse(body || '[]'));
        reply = { ok: true, value: value === undefined ? null : value };
      } catch (e) {
        reply = { ok: false, error: String(e && e.message || e) };
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(reply));
    });
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve(server)));
}

if (require.main === module) {
  startPreview({ port: Number(process.env.PORT) || 8787, clockControl: process.env.PREVIEW_CLOCK_CONTROL === '1' }).then((s) => {
    console.log(`Study app preview on http://localhost:${s.address().port} (Demo bank, in memory)`);
  });
}

module.exports = { startPreview };
