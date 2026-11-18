// Loads every server file the way Apps Script does: one shared global scope.
// Each file's export guard hands its top-level names to Node; they are put on
// globalThis so cross-file references resolve as they do in Apps Script.
const fs = require('node:fs');
const path = require('node:path');

const serverDir = path.join(__dirname, '..', 'server');
for (const file of fs.readdirSync(serverDir).filter((f) => f.endsWith('.js')).sort()) {
  Object.assign(globalThis, require(path.join(serverDir, file)));
}

module.exports = { makeServer: globalThis.makeServer_ };
