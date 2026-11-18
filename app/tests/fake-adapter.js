// In-memory test build of the adapter. Same shape as appsScriptAdapter_ in
// server/adapter.js, plus test controls to set up a sheet and read it back.

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function dateInZone(iso, timeZone) {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date(iso));
}

function makeFakeAdapter(options = {}) {
  const state = {
    tabs: new Map(), // name -> {values: string[][], plainText, frozenRows}
    props: {},
    now: options.now || '2026-11-18T08:00:00Z',
    timeZone: options.timeZone || 'Etc/UTC',
    lockHeldElsewhere: false,
    lockTaken: false,
    spreadsheetUrl: options.spreadsheetUrl || 'https://docs.google.com/spreadsheets/d/fake/edit',
    webAppUrl: options.webAppUrl === undefined ? 'https://script.google.com/macros/s/fake/exec' : options.webAppUrl,
  };
  const random = mulberry32(options.seed === undefined ? 1 : options.seed);

  function tab(name) {
    const t = state.tabs.get(name);
    if (!t) throw new Error('No tab: ' + name);
    return t;
  }

  function headerOf(t) {
    return t.values.length ? t.values[0] : [];
  }

  function toRow(headers, obj) {
    return headers.map((h) => (obj[h] === undefined || obj[h] === null ? '' : String(obj[h])));
  }

  const adapter = {
    tabs: {
      exists: (name) => state.tabs.has(name),
      read(name) {
        const t = tab(name);
        const headers = headerOf(t).slice();
        const rows = t.values.slice(1).map((r) => {
          const o = {};
          headers.forEach((h, i) => { o[h] = r[i] === undefined ? '' : r[i]; });
          return o;
        });
        return { headers, rows };
      },
      create(name, headers) {
        if (state.tabs.has(name)) throw new Error('Tab exists: ' + name);
        const withHeader = headers && headers.length > 0;
        state.tabs.set(name, {
          values: withHeader ? [headers.slice()] : [],
          plainText: withHeader,
          frozenRows: withHeader ? 1 : 0,
        });
      },
      append(name, rows) {
        const t = tab(name);
        const headers = headerOf(t);
        rows.forEach((o) => t.values.push(toRow(headers, o)));
      },
      rewrite(name, rows) {
        const t = tab(name);
        const headers = headerOf(t);
        t.values = [headers].concat(rows.map((o) => toRow(headers, o)));
      },
      clearBody(name) {
        const t = tab(name);
        t.values = t.values.slice(0, 1);
      },
    },
    props: {
      get: (key) => (Object.prototype.hasOwnProperty.call(state.props, key) ? state.props[key] : null),
      set: (key, value) => { state.props[key] = String(value); },
    },
    lock: {
      take(waitMs) {
        if (state.lockHeldElsewhere || state.lockTaken) return false;
        state.lockTaken = true;
        return true;
      },
      release() { state.lockTaken = false; },
    },
    clock: {
      now: () => state.now,
      today: () => dateInZone(state.now, state.timeZone),
      dateOf: (iso) => dateInZone(iso, state.timeZone),
    },
    random: () => random(),
    urls: {
      spreadsheet: () => state.spreadsheetUrl,
      webApp: () => state.webAppUrl,
    },
  };

  const controls = {
    addTab(name, values = [], extra = {}) {
      state.tabs.set(name, {
        values: values.map((r) => r.slice()),
        plainText: !!extra.plainText,
        frozenRows: extra.frozenRows || 0,
      });
    },
    removeTab: (name) => { state.tabs.delete(name); },
    tabNames: () => Array.from(state.tabs.keys()),
    values: (name) => tab(name).values.map((r) => r.slice()),
    tabInfo: (name) => ({ plainText: tab(name).plainText, frozenRows: tab(name).frozenRows }),
    props: state.props,
    setNow: (iso) => { state.now = iso; },
    holdLockElsewhere: (on = true) => { state.lockHeldElsewhere = on; },
  };

  return { adapter, ...controls };
}

module.exports = { makeFakeAdapter };
