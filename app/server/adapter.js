// Apps Script build of the adapter: the one place server code touches
// SpreadsheetApp, PropertiesService, LockService, ScriptApp and Utilities.
// tests/fake-adapter.js is the in-memory build with the same shape.

function appsScriptAdapter_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var scriptLock = LockService.getScriptLock();

  function sheet(name) {
    var sh = ss.getSheetByName(name);
    if (!sh) throw new Error('No tab: ' + name);
    return sh;
  }

  function headerOf(sh) {
    var lastCol = sh.getLastColumn();
    if (sh.getLastRow() < 1 || lastCol < 1) return [];
    return sh.getRange(1, 1, 1, lastCol).getValues()[0].map(String);
  }

  // Empties every row below the header, across the header's columns.
  function clearBelowHeader(sh, width) {
    if (sh.getLastRow() > 1 && width > 0) sh.getRange(2, 1, sh.getLastRow() - 1, width).clearContent();
  }

  function toValues(headers, rows) {
    return rows.map(function (o) {
      return headers.map(function (h) {
        return o[h] === undefined || o[h] === null ? '' : String(o[h]);
      });
    });
  }

  // Writes values from row `startRow` down in one batch call, as plain text.
  function writeBlock(sh, startRow, values) {
    if (!values.length) return;
    var need = startRow + values.length - 1;
    if (need > sh.getMaxRows()) sh.insertRowsAfter(sh.getMaxRows(), need - sh.getMaxRows());
    var range = sh.getRange(startRow, 1, values.length, values[0].length);
    range.setNumberFormat('@');
    range.setValues(values);
  }

  function timeZone() {
    return ss.getSpreadsheetTimeZone();
  }

  function isoNow() {
    return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  }

  return {
    tabs: {
      exists: function (name) {
        return ss.getSheetByName(name) !== null;
      },
      read: function (name) {
        var sh = sheet(name);
        var lastRow = sh.getLastRow();
        var lastCol = sh.getLastColumn();
        if (lastRow < 1 || lastCol < 1) return { headers: [], rows: [] };
        var values = sh.getRange(1, 1, lastRow, lastCol).getValues();
        var headers = values[0].map(String);
        var rows = values.slice(1).map(function (r) {
          var o = {};
          headers.forEach(function (h, i) { o[h] = r[i]; });
          return o;
        });
        return { headers: headers, rows: rows };
      },
      // Creates a tab. With headers: writes row 1, sets the whole tab to plain
      // text and freezes row 1. With none: an empty tab, untouched.
      create: function (name, headers) {
        var sh = ss.insertSheet(name);
        if (headers && headers.length) {
          sh.getRange(1, 1, sh.getMaxRows(), sh.getMaxColumns()).setNumberFormat('@');
          sh.getRange(1, 1, 1, headers.length).setValues([headers]);
          sh.setFrozenRows(1);
        }
      },
      append: function (name, rows) {
        var sh = sheet(name);
        writeBlock(sh, sh.getLastRow() + 1, toValues(headerOf(sh), rows));
      },
      rewrite: function (name, rows) {
        var sh = sheet(name);
        var headers = headerOf(sh);
        clearBelowHeader(sh, headers.length);
        writeBlock(sh, 2, toValues(headers, rows));
      },
      clearBody: function (name) {
        var sh = sheet(name);
        clearBelowHeader(sh, headerOf(sh).length);
      },
    },
    props: {
      get: function (key) {
        return PropertiesService.getScriptProperties().getProperty(key);
      },
      set: function (key, value) {
        PropertiesService.getScriptProperties().setProperty(key, String(value));
      },
    },
    lock: {
      take: function (waitMs) {
        return scriptLock.tryLock(waitMs);
      },
      release: function () {
        scriptLock.releaseLock();
      },
    },
    clock: {
      now: isoNow,
      today: function () {
        return Utilities.formatDate(new Date(), timeZone(), 'yyyy-MM-dd');
      },
      dateOf: function (iso) {
        return Utilities.formatDate(new Date(iso), timeZone(), 'yyyy-MM-dd');
      },
    },
    random: function () {
      return Math.random();
    },
    urls: {
      spreadsheet: function () {
        return ss.getUrl();
      },
      // The /exec URL doGet saved on the last page load. Empty until the web
      // app has been opened once. ScriptApp.getService().getUrl() called from
      // a menu dialog returns a dead URL (ticket 45), so the menu never calls
      // it; only doGet does.
      webApp: function () {
        return PropertiesService.getScriptProperties().getProperty('web_app_url') || '';
      },
    },
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { appsScriptAdapter_: appsScriptAdapter_ };
}
