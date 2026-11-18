// Smoke test for scripts/preview_app.js, the local preview used for README captures.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { startPreview } = require(path.join(__dirname, '..', '..', 'scripts', 'preview_app.js'));

test('the preview serves the inlined page and runs server calls on the Demo bank', async () => {
  const server = await startPreview({ port: 0 });
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const page = await (await fetch(base + '/')).text();
    assert.ok(!page.includes('<?!='), 'every include is inlined');
    assert.ok(page.includes('window.google'), 'the google.script.run stub is injected');

    const rpc = async (fn, args = []) =>
      (await fetch(`${base}/rpc/${fn}`, { method: 'POST', body: JSON.stringify(args) })).json();

    const load = await rpc('load');
    assert.equal(load.ok, true);
    assert.equal(load.value.screen, 'home');
    assert.equal(load.value.bank.length, 25);

    const denied = await fetch(`${base}/rpc/rebuildStudyState`, { method: 'POST', body: '[]' });
    assert.equal(denied.status, 404, 'menu items are not callable');
  } finally {
    server.close();
  }
});
