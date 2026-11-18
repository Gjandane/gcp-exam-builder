// Server interface. makeServer_(adapter) returns the functions the client calls
// over google.script.run; server/main.js binds them to the Apps Script adapter.
// All sheet, property, lock, clock and random access goes through `adapter`.

var QUESTIONS_TAB_ = 'Questions';
var ATTEMPTS_TAB_ = 'Attempts';
var STATE_TAB_ = 'QuestionState';
var REPORTS_TAB_ = 'Reports';
var REPORT_NOTE_MAX_ = 1000;

// Leitner intervals in days for boxes 1 to 5, spec 0002 Leitner.
var LEITNER_DAYS_ = { 1: 1, 2: 2, 3: 4, 4: 8, 5: 16 };

// The QuestionState cache fields the rebuild rewrites; the rest live only there.
var REBUILT_FIELDS_ = ['box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result'];

// The 30 bank columns, spec 0002 Bank check and 0001 CSV contract.
var BANK_COLUMNS_ = [
  'id', 'exam', 'status', 'subdomain', 'subdomain_title', 'question',
  'choice_a', 'choice_b', 'choice_c', 'choice_d', 'choice_e', 'choice_f',
  'answer',
  'explanation_a', 'explanation_b', 'explanation_c', 'explanation_d', 'explanation_e', 'explanation_f',
  'lineage', 'sources', 'source_urls', 'source_answers', 'uncertain', 'answer_by', 'explanation_by',
  'derived_from', 'updated_at', 'rechecked_at', 'recheck_note',
];

// Cells that must hold text: a number, date or boolean means "Convert text" was on.
var TEXT_ONLY_COLUMNS_ = ['id', 'subdomain', 'answer', 'uncertain', 'updated_at'];

// Tabs whose question_id column can name a question missing from the bank.
var HISTORY_TABS_ = ['QuestionState', 'Attempts', 'Reports', 'MockTestItems'];

var REFUSAL_LIST_LIMIT_ = 20;

var CONVERTED_LEAD_ = "Some cells were converted on import. Import again with 'Convert text to numbers, dates, and formulas' unticked.";

// The import steps: one constant, word for word as spec 0002 and
// templates/import-steps.txt in the skill have it. The menu dialog, the home
// panel and the refusal screen all show it. <slug> stays literal.
var IMPORT_STEPS_ = [
  'Import into the sheet:',
  '1. Open the spreadsheet and select the Questions tab.',
  '2. File > Import > Upload, pick export/<slug>-questions.csv.',
  '3. Import location: "Replace current sheet". Never "Replace spreadsheet".',
  '4. Separator type: Comma.',
  '5. Untick "Convert text to numbers, dates, and formulas".',
].join('\n');

// App tabs and their header rows, spec 0002, Sheet tabs.
var APP_TABS_ = {
  Settings: ['key', 'value'],
  QuestionState: ['question_id', 'box', 'due_at', 'attempts', 'correct_count', 'last_seen_at', 'last_result', 'bookmarked', 'note', 'note_updated_at'],
  Attempts: ['answered_at', 'question_id', 'mode', 'test_id', 'selected', 'correct_answer', 'result', 'question_updated_at', 'flagged'],
  MockTests: ['test_id', 'status', 'started_at', 'submitted_at', 'question_count', 'minutes_allowed', 'seconds_left', 'correct_count', 'score_pct'],
  MockTestItems: ['test_id', 'position', 'question_id', 'choice_order', 'selected', 'flagged', 'question_updated_at'],
  Reports: ['report_id', 'reported_at', 'question_id', 'note', 'question_updated_at', 'status', 'resolved_at', 'resolution'],
};

// The "set up" mark: a script property, outside every tab (spec 0002, [G6]).
var SETUP_MARK_KEY_ = 'setup_done_at';

// Every write takes the script lock, waiting up to 10 seconds (spec 0002, [G17]).
var LOCK_WAIT_MS_ = 10000;

// Settings, spec 0002 Settings and Settings screen. The five fields the screen edits, in order.
var SETTINGS_TAB_ = 'Settings';
var SETTINGS_FIELDS_ = ['exam_name', 'exam_date', 'mock_question_count', 'mock_minutes', 'section_weights'];
var SETTINGS_DEFAULTS_ = { mock_question_count: '50', mock_minutes: '120' };
var SCHEMA_VERSION_ = '1';
var EXAM_NAME_MAX_ = 100;

var FIELD_RULES_ = {
  exam_name: 'Required, at most 100 characters.',
  exam_date: 'A real date as YYYY-MM-DD. A past date is allowed.',
  mock_question_count: 'A whole number from 1 to 200.',
  mock_minutes: 'A whole number from 1 to 600.',
};

var WEIGHTS_HINT_ = "Paste the `section_weights` line that `/exam-bank <exam> export` prints. Leave empty to follow the bank's own mix.";
var WEIGHTS_PREFIX_ = /^\s*section_weights:/;
var MS_PER_DAY_ = 86400000;
var BUSY_MESSAGE_ = 'The sheet is busy. Try again.';
var STATE_REBUILT_TEXT_ = 'The QuestionState tab was missing. Boxes and due dates were rebuilt from your attempts. Bookmarks and notes could not be recovered.';

function makeServer_(adapter) {
  // Runs write() under the script lock. Returns write()'s result, or the busy
  // error when the lock is not free within the wait.
  function withWriteLock(write) {
    if (!adapter.lock.take(LOCK_WAIT_MS_)) return { error: 'busy', message: BUSY_MESSAGE_ };
    try {
      return write();
    } finally {
      adapter.lock.release();
    }
  }

  function missingTabs() {
    var missing = [];
    if (!adapter.tabs.exists(QUESTIONS_TAB_)) missing.push(QUESTIONS_TAB_);
    Object.keys(APP_TABS_).forEach(function (name) {
      if (!adapter.tabs.exists(name)) missing.push(name);
    });
    return missing;
  }

  // Load step 2: create each missing tab, then set the mark when absent.
  // Returns true when it recreated QuestionState on a sheet that has Attempts
  // rows and rebuilt it (spec 0002, Rebuild).
  function ensureTabs() {
    var stateMissing = !adapter.tabs.exists(STATE_TAB_);
    missingTabs().forEach(function (name) {
      // Questions is created empty: the app writes nothing to it (ADR 0003).
      adapter.tabs.create(name, name === QUESTIONS_TAB_ ? [] : APP_TABS_[name]);
    });
    if (!adapter.props.get(SETUP_MARK_KEY_)) adapter.props.set(SETUP_MARK_KEY_, adapter.clock.now());
    if (stateMissing && adapter.tabs.read(ATTEMPTS_TAB_).rows.length) {
      rebuildRows();
      return true;
    }
    return false;
  }

  // Load step 1: the mark exists and Attempts is gone, so "Replace spreadsheet"
  // wiped the app tabs. Create nothing.
  function isWiped() {
    return !!adapter.props.get(SETUP_MARK_KEY_) && !adapter.tabs.exists(ATTEMPTS_TAB_);
  }

  function wipeScreen() {
    return { screen: 'wipe', spreadsheetUrl: adapter.urls.spreadsheet() };
  }

  function isEmptyCell(value) {
    return value === '' || value === null || value === undefined;
  }

  // Empty, or text of spaces only.
  function isBlank(value) {
    return isEmptyCell(value) || (typeof value === 'string' && value.trim() === '');
  }

  // Load step 4. `table` is the Questions tab read as {headers, rows}. Returns
  // the refusal messages (none when the bank passes) and whether any case 5 fired.
  function checkBank(table) {
    if (!table.headers.length || !table.rows.length) {
      return { messages: ['The Questions tab is empty.'], converted: false };
    }
    var missing = BANK_COLUMNS_.filter(function (name) { return table.headers.indexOf(name) < 0; });
    if (missing.length) {
      return {
        messages: missing.map(function (name) { return 'Missing column: `' + name + '`'; }),
        converted: false,
      };
    }

    var messages = [];
    var converted = false;
    var firstSeen = {};
    var activeCount = 0;
    table.rows.forEach(function (row, i) {
      var n = i + 2; // sheet row number, header = 1
      TEXT_ONLY_COLUMNS_.forEach(function (name) {
        if (typeof row[name] !== 'string' && !isEmptyCell(row[name])) {
          messages.push('Row ' + n + ': `' + name + '` is not text');
          converted = true;
        }
      });
      if (isBlank(row.id)) {
        messages.push('Row ' + n + ': empty id');
      } else if (typeof row.id === 'string') {
        if (firstSeen[row.id] === undefined) firstSeen[row.id] = n;
        else messages.push('Row ' + n + ': duplicate id `' + row.id + '`, first seen in row ' + firstSeen[row.id]);
      }
      if (row.status !== 'active' && row.status !== 'retired') {
        messages.push('Row ' + n + ': status `' + row.status + '`');
      }
      if (row.status === 'active') {
        activeCount++;
        if (typeof row.answer === 'string') {
          row.answer.split(',').forEach(function (part) {
            var letter = part.trim();
            var cell = /^[A-F]$/.test(letter) ? row['choice_' + letter.toLowerCase()] : '';
            if (isBlank(cell)) {
              messages.push('Row ' + n + ': answer `' + letter + '` has no choice');
            }
          });
        }
      }
    });
    if (activeCount === 0) messages.push('No active questions.');
    return { messages: messages, converted: converted };
  }

  function refusalScreen(check) {
    return {
      screen: 'refused',
      lead: check.converted ? CONVERTED_LEAD_ : '',
      messages: check.messages.slice(0, REFUSAL_LIST_LIMIT_),
      more: Math.max(0, check.messages.length - REFUSAL_LIST_LIMIT_),
      importSteps: IMPORT_STEPS_,
      spreadsheetUrl: adapter.urls.spreadsheet(),
    };
  }

  // Distinct question IDs in the history tabs that no Questions row carries.
  function countOrphans(bankIds) {
    var orphans = {};
    HISTORY_TABS_.forEach(function (name) {
      adapter.tabs.read(name).rows.forEach(function (row) {
        var id = row.question_id;
        if (typeof id === 'string' && id !== '' && !bankIds[id]) orphans[id] = true;
      });
    });
    return Object.keys(orphans).length;
  }

  // A bank row as the client keeps it: the 30 known columns, as text.
  function bankRow(row) {
    var out = {};
    BANK_COLUMNS_.forEach(function (name) {
      out[name] = isEmptyCell(row[name]) ? '' : String(row[name]);
    });
    return out;
  }

  // Newest updated_at among the rows, as a date in the spreadsheet's time zone.
  function newestUpdate(rows) {
    var newest = '';
    rows.forEach(function (row) {
      var stamp = row.updated_at;
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(stamp) && stamp > newest) newest = stamp;
    });
    return newest ? adapter.clock.dateOf(newest) : '';
  }

  // The question IDs with an open Report, in sheet order.
  function openReportIds() {
    var seen = {};
    var ids = [];
    adapter.tabs.read(REPORTS_TAB_).rows.forEach(function (row) {
      if (row.status === 'open' && typeof row.question_id === 'string' && row.question_id !== '' && !seen[row.question_id]) {
        seen[row.question_id] = true;
        ids.push(row.question_id);
      }
    });
    return ids;
  }

  function homeScreen(table, settings, resolvedReports, rebuilt) {
    var bank = table.rows.map(bankRow);
    var bankIds = {};
    bank.forEach(function (row) { bankIds[row.id] = true; });
    var orphaned = countOrphans(bankIds);
    var unknown = table.headers.filter(function (h) { return h !== '' && BANK_COLUMNS_.indexOf(h) < 0; }).length;

    var warnings = [];
    if (resolvedReports > 0) {
      warnings.push({
        id: 'reports_rechecked',
        text: resolvedReports + (resolvedReports === 1 ? ' Report was' : ' Reports were') +
          " re-checked. Open a question's Report panel to read the result.",
      });
    }
    if (rebuilt) warnings.push({ id: 'state_rebuilt', text: STATE_REBUILT_TEXT_ });
    if (unknown > 0) {
      warnings.push({ id: 'unknown_columns', text: 'The bank has ' + unknown + ' unknown columns. The app ignores them.' });
    }
    if (orphaned > 0) {
      warnings.push({ id: 'orphans', text: orphaned + ' questions with study history are no longer in the bank. Their history is kept.' });
    }
    var activeCount = bank.filter(function (r) { return r.status === 'active'; }).length;
    if (activeCount < +settings.mock_question_count) {
      warnings.push({
        id: 'few_active',
        text: 'The bank has ' + activeCount + ' active questions. A Mock Test of ' + settings.mock_question_count + ' will be shorter.',
      });
    }
    var today = adapter.clock.today();
    return {
      screen: 'home',
      today: today,
      header: { examName: settings.exam_name, examDate: settings.exam_date, daysLeft: daysLeftText(settings.exam_date, today) },
      settings: settingsForScreen(settings),
      hints: { section_weights: WEIGHTS_HINT_ },
      bank: bank,
      states: statesForClient(bank, adapter.tabs.read(STATE_TAB_).rows, srContext(settings.exam_date)),
      counts: reviewCounts(table.rows, settings.exam_date),
      openReports: openReportIds(),
      warnings: warnings,
      bankLine: {
        active: activeCount,
        retired: bank.filter(function (r) { return r.status === 'retired'; }).length,
        orphaned: orphaned,
        updated: newestUpdate(bank),
      },
      importSteps: IMPORT_STEPS_,
      spreadsheetUrl: adapter.urls.spreadsheet(),
      mockTest: mockSummary(table.rows),
    };
  }

  // ---- Settings

  // The Settings tab as {key: text}, first row of each key. Cells read as text,
  // so a hand-typed 90 equals '90'.
  function readSettings() {
    var map = {};
    adapter.tabs.read(SETTINGS_TAB_).rows.forEach(function (row) {
      var key = String(row.key).trim();
      if (key !== '' && map[key] === undefined) map[key] = isEmptyCell(row.value) ? '' : String(row.value);
    });
    return map;
  }

  // Sets each key in `changes`: every row of that key, or a new row when none.
  function writeSettings(changes) {
    var rows = adapter.tabs.read(SETTINGS_TAB_).rows;
    var seen = {};
    rows.forEach(function (row) {
      var key = String(row.key).trim();
      if (Object.prototype.hasOwnProperty.call(changes, key)) {
        row.value = changes[key];
        seen[key] = true;
      }
    });
    Object.keys(changes).forEach(function (key) {
      if (!seen[key]) rows.push({ key: key, value: changes[key] });
    });
    adapter.tabs.rewrite(SETTINGS_TAB_, rows);
  }

  // Load step 3. A filled schema_version other than 1 stops; an empty one is written as 1.
  function layoutStop() {
    var version = (readSettings().schema_version || '').trim();
    if (version === SCHEMA_VERSION_) return null;
    if (version !== '') {
      return {
        screen: 'version',
        message: 'This sheet was set up by a different version of the app (layout ' + version + '). Update the app code, see the README, Upkeep.',
      };
    }
    return withWriteLock(function () {
      writeSettings({ schema_version: SCHEMA_VERSION_ });
      return null;
    });
  }

  function isRealDate(text) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
    if (!m) return false;
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3];
  }

  function integerInRange(text, min, max) {
    return /^\d+$/.test(text) && +text >= min && +text <= max;
  }

  // Section number of a bank row: the part of `subdomain` before the first dot.
  function sectionOf(row) {
    return isBlank(row.subdomain) ? '' : String(row.subdomain).split('.')[0].trim();
  }

  // Checks a weights string against the bank. Returns {error} or {value} (the stored form).
  function checkWeights(text, bankRows) {
    if (text === '') return { value: '' };
    var inBank = {};
    var active = {};
    bankRows.forEach(function (row) {
      var n = sectionOf(row);
      if (n === '') return;
      inBank[n] = true;
      if (row.status === 'active') active[n] = true;
    });
    var seen = {};
    var pairs = [];
    var anyPositive = false;
    var parts = text.split(',');
    for (var i = 0; i < parts.length; i++) {
      var m = /^\s*(\d+)\s*:\s*(\S+)\s*$/.exec(parts[i]);
      if (!m) return { error: 'Use pairs like 1:13,2:16 separated by commas, with no empty part.' };
      if (!/^\d+(\.\d+)?$/.test(m[2])) return { error: 'Each weight must be a number of 0 or more.' };
      if (!inBank[m[1]]) return { error: 'Section ' + m[1] + ' is not in the bank.' };
      if (seen[m[1]]) return { error: 'Section ' + m[1] + ' appears twice.' };
      seen[m[1]] = true;
      if (parseFloat(m[2]) > 0) anyPositive = true;
      pairs.push(m[1] + ':' + m[2]);
    }
    var missing = Object.keys(active).filter(function (n) { return !seen[n]; });
    if (missing.length) return { error: 'Section ' + missing[0] + ' has active questions and needs a weight.' };
    if (!anyPositive) return { error: 'At least one weight must be above 0.' };
    return { value: pairs.join(',') };
  }

  // Validates the five fields. `stripPrefix` is true on Save only.
  // Returns {errors, clean}: errors by field, and the trimmed values to store.
  function validateSettings(values, bankRows, stripPrefix) {
    var errors = {};
    var clean = {};
    SETTINGS_FIELDS_.forEach(function (key) {
      clean[key] = isEmptyCell(values[key]) ? '' : String(values[key]).trim();
    });
    if (clean.exam_name === '' || clean.exam_name.length > EXAM_NAME_MAX_) errors.exam_name = FIELD_RULES_.exam_name;
    if (!isRealDate(clean.exam_date)) errors.exam_date = FIELD_RULES_.exam_date;
    if (!integerInRange(clean.mock_question_count, 1, 200)) errors.mock_question_count = FIELD_RULES_.mock_question_count;
    if (!integerInRange(clean.mock_minutes, 1, 600)) errors.mock_minutes = FIELD_RULES_.mock_minutes;
    var weights = clean.section_weights;
    if (stripPrefix) weights = weights.replace(WEIGHTS_PREFIX_, '').trim();
    var checked = checkWeights(weights, bankRows);
    if (checked.error) errors.section_weights = checked.error;
    else clean.section_weights = checked.value;
    return { errors: errors, clean: clean };
  }

  // The five values as the screen shows them: stored text, or the default for a missing count or minutes.
  function settingsForScreen(map) {
    var out = {};
    SETTINGS_FIELDS_.forEach(function (key) {
      out[key] = map[key] !== undefined ? map[key] : (SETTINGS_DEFAULTS_[key] || '');
    });
    return out;
  }

  function settingsScreen(map, errors, mode) {
    return {
      screen: 'settings',
      mode: mode,
      values: settingsForScreen(map),
      errors: errors,
      hints: { section_weights: WEIGHTS_HINT_ },
    };
  }

  function daysLeftText(examDate, today) {
    var days = Math.round((Date.parse(examDate + 'T00:00:00Z') - Date.parse(today + 'T00:00:00Z')) / MS_PER_DAY_);
    if (days > 0) return days + (days === 1 ? ' day left' : ' days left');
    return days === 0 ? 'Exam is today' : 'Exam date passed · update in Settings';
  }

  function needsSetup() {
    return missingTabs().length > 0 || !adapter.props.get(SETUP_MARK_KEY_);
  }

  function load() {
    if (isWiped()) return wipeScreen();
    var rebuilt = false;
    if (needsSetup()) {
      // Check again under the lock: another load may have run in between.
      var blocked = withWriteLock(function () {
        if (isWiped()) return wipeScreen();
        rebuilt = ensureTabs();
        return null;
      });
      if (blocked) return blocked;
    }
    var stop = layoutStop();
    if (stop) return stop;
    var table = adapter.tabs.read(QUESTIONS_TAB_);
    var check = checkBank(table);
    if (check.messages.length) return refusalScreen(check);

    // Load step 5. No row for any of the five fields is first open.
    var stored = readSettings();
    var anyStored = SETTINGS_FIELDS_.some(function (key) { return stored[key] !== undefined; });
    if (!anyStored) return settingsScreen(stored, {}, 'setup');
    // A missing weights row means empty weights.
    var toCheck = {};
    SETTINGS_FIELDS_.forEach(function (key) { toCheck[key] = stored[key] === undefined ? '' : stored[key]; });
    var verdict = validateSettings(toCheck, table.rows, false);
    if (Object.keys(verdict.errors).length) return settingsScreen(stored, verdict.errors, 'fix');

    // Load step 6: finish a submit cut off midway.
    var finished = finishHalfSubmitted();
    if (finished) return finished;

    // Load step 7: resolve the Reports a re-check has answered.
    var resolved = resolveReports(table.rows);
    if (resolved.error) return resolved;
    return homeScreen(table, verdict.clean, resolved.count, rebuilt);
  }

  // ---- Reports

  // Epoch ms of a stored timestamp, or NaN.
  function stampMs(text) {
    return typeof text === 'string' && text.trim() !== '' ? Date.parse(text.trim()) : NaN;
  }

  // The rows of `reports` that a bank row's rechecked_at now answers.
  function reportsToResolve(reports, bankRows) {
    var byId = {};
    bankRows.forEach(function (row) { if (typeof row.id === 'string') byId[row.id] = row; });
    return reports.filter(function (report) {
      var bankRow = byId[report.question_id];
      return report.status === 'open' && bankRow && stampMs(bankRow.rechecked_at) > stampMs(report.reported_at);
    });
  }

  // `UTC time as YYYYMMDDTHHMMSSZ`, the compact form of test_id.
  function compactStamp(iso) {
    return iso.replace(/[-:]/g, '');
  }

  // Resolve rule, spec 0002 Report loop. Takes the lock only when a row will change.
  function resolveReports(bankRows) {
    if (!reportsToResolve(adapter.tabs.read(REPORTS_TAB_).rows, bankRows).length) return { count: 0 };
    var out = withWriteLock(function () {
      var reports = adapter.tabs.read(REPORTS_TAB_).rows;
      var due = reportsToResolve(reports, bankRows);
      var byId = {};
      bankRows.forEach(function (row) { if (typeof row.id === 'string') byId[row.id] = row; });
      var now = adapter.clock.now();
      due.forEach(function (report) {
        report.status = 'resolved';
        report.resolved_at = now;
        var note = byId[report.question_id].recheck_note;
        report.resolution = isEmptyCell(note) ? '' : String(note);
      });
      if (due.length) adapter.tabs.rewrite(REPORTS_TAB_, reports);
      return { count: due.length };
    });
    return out;
  }

  // A Reports row as the client gets it: the eight columns, as text.
  function reportForClient(row) {
    var out = {};
    APP_TABS_[REPORTS_TAB_].forEach(function (name) {
      out[name] = isEmptyCell(row[name]) ? '' : String(row[name]);
    });
    return out;
  }

  function refuseReport(message) {
    return { error: 'bad_report', message: message };
  }

  // Creates the question's open Report, or edits it and moves reported_at to now.
  function saveReport(questionId, note) {
    var text = typeof note === 'string' ? note.trim() : '';
    if (text === '') return refuseReport('Say what looks wrong.');
    if (text.length > REPORT_NOTE_MAX_) return refuseReport('The note is at most 1,000 characters.');
    return withWriteLock(function () {
      var bankRow = adapter.tabs.read(QUESTIONS_TAB_).rows.filter(function (row) { return row.id === questionId; })[0];
      if (!bankRow) return refuseReport('This question is not in the bank.');
      var now = adapter.clock.now();
      var reports = adapter.tabs.read(REPORTS_TAB_).rows;
      var open = reports.filter(function (row) { return row.question_id === questionId && row.status === 'open'; })[0];
      if (open) {
        open.note = text;
        open.reported_at = now;
        adapter.tabs.rewrite(REPORTS_TAB_, reports);
        return reportForClient(open);
      }
      var created = {
        report_id: 'r_' + compactStamp(now), reported_at: now, question_id: questionId, note: text,
        question_updated_at: isEmptyCell(bankRow.updated_at) ? '' : String(bankRow.updated_at),
        status: 'open', resolved_at: '', resolution: '',
      };
      adapter.tabs.append(REPORTS_TAB_, [created]);
      return reportForClient(created);
    });
  }

  // The open row and the last resolved row of one question, null when none.
  function getReports(questionId) {
    var open = null;
    var resolved = null;
    adapter.tabs.read(REPORTS_TAB_).rows.forEach(function (row) {
      if (row.question_id !== questionId) return;
      if (row.status === 'open' && !open) open = row;
      // The latest resolved_at wins; a tie goes to the later row.
      else if (row.status === 'resolved' && (!resolved || !(stampMs(row.resolved_at) < stampMs(resolved.resolved_at)))) resolved = row;
    });
    return { open: open ? reportForClient(open) : null, resolved: resolved ? reportForClient(resolved) : null };
  }

  function saveSettings(values) {
    // A wiped or half-built sheet has no Settings tab to write: load says why.
    if (isWiped() || !adapter.tabs.exists(SETTINGS_TAB_) || !adapter.tabs.exists(QUESTIONS_TAB_)) return load();
    var stop = layoutStop();
    if (stop) return stop;
    var bankRows = adapter.tabs.read(QUESTIONS_TAB_).rows;
    var verdict = validateSettings(values || {}, bankRows, true);
    if (Object.keys(verdict.errors).length) return { fieldErrors: verdict.errors };
    var blocked = withWriteLock(function () {
      writeSettings(verdict.clean);
      return null;
    });
    return blocked || load();
  }

  // ---- Review mode

  // Active bank rows with an id, in bank order.
  function activeRows(rows) {
    return rows.filter(function (row) { return row.status === 'active' && typeof row.id === 'string' && row.id !== ''; });
  }

  // QuestionState rows by question_id, first row of each id.
  function statesById(rows) {
    var map = {};
    rows.forEach(function (row) {
      var id = row.question_id;
      if (typeof id === 'string' && id !== '' && !map[id]) map[id] = row;
    });
    return map;
  }

  function boxOf(row) {
    var box = row ? parseInt(row.box, 10) : 0;
    return box >= 1 && box <= 5 ? box : 0;
  }

  // Letters as a sorted, de-duplicated array, from "C, a" or ['C','A'].
  function letterList(value) {
    var parts = Array.isArray(value) ? value : String(isEmptyCell(value) ? '' : value).split(',');
    var seen = {};
    parts.forEach(function (part) {
      var letter = String(part).trim().toUpperCase();
      if (letter !== '') seen[letter] = true;
    });
    return Object.keys(seen).sort();
  }

  function addDays(date, days) {
    var d = new Date(Date.parse(date + 'T00:00:00Z'));
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  // The latest cap date (the day before the exam), or '' when the cap is off:
  // after the exam date, or with no valid exam date.
  function capDate(examDate, today) {
    if (!isRealDate(examDate) || today > examDate) return '';
    return addDays(examDate, -1);
  }

  // The correct_answer of each question's latest non-skipped Attempts row, in
  // sheet order (mock rows of one test share an answered_at), as joined letters.
  function lastGradedAnswers(attemptRows) {
    var map = {};
    attemptRows.forEach(function (row) {
      if (row.result === 'correct' || row.result === 'wrong') map[row.question_id] = letterList(row.correct_answer).join(',');
    });
    return map;
  }

  // Reads what the effective state needs: the cap, the last graded answers, today.
  function srContext(examDate) {
    var today = adapter.clock.today();
    return {
      today: today,
      cap: capDate(examDate, today),
      lastAnswers: lastGradedAnswers(adapter.tabs.read(ATTEMPTS_TAB_).rows),
    };
  }

  // The box and due date a seen question has today: the stored row with the
  // exam-date cap and the changed-answer rule applied. Read time only.
  function effectiveState(row, bankAnswer, ctx) {
    var box = boxOf(row);
    if (box === 0) return { box: 0, due: '' };
    var last = ctx.lastAnswers[row.question_id];
    if (last !== undefined && bankAnswer !== undefined && last !== letterList(bankAnswer).join(',')) {
      return { box: 1, due: ctx.today };
    }
    var due = String(row.due_at);
    if (!isRealDate(due)) due = ctx.today;
    if (ctx.cap && due > ctx.cap) due = ctx.cap;
    return { box: box, due: due };
  }

  // A QuestionState row as the client gets it: stored columns as text, plus
  // the effective box and due date.
  function stateForClient(row, eff) {
    var out = {};
    APP_TABS_[STATE_TAB_].forEach(function (name) {
      out[name] = isEmptyCell(row[name]) ? '' : String(row[name]);
    });
    out.effective_box = eff.box;
    out.effective_due_at = eff.due;
    return out;
  }

  // Every QuestionState row by id, in client form.
  function statesForClient(bankRows, stateRows, ctx) {
    var answers = {};
    bankRows.forEach(function (row) { answers[row.id] = row.answer; });
    var out = {};
    var byId = statesById(stateRows);
    Object.keys(byId).forEach(function (id) {
      out[id] = stateForClient(byId[id], effectiveState(byId[id], answers[id], ctx));
    });
    return out;
  }

  // The Leitner table, spec 0002 Leitner, for one graded answer. `eff` is the
  // box and due date the question has at grading time; `today` is the grading
  // date. Moves the row's box and due_at, bumps the counters, sets last_seen_at
  // and last_result. The live path and the rebuild both call this.
  function applyGraded(row, result, seenAt, today, eff) {
    if (result === 'wrong') {
      row.box = '1';
      row.due_at = addDays(today, 1);
    } else if (eff.box === 0 || eff.due <= today) {
      var box = Math.min(eff.box + 1, 5);
      row.box = String(box);
      row.due_at = addDays(today, LEITNER_DAYS_[box]);
    }
    row.attempts = String((parseInt(row.attempts, 10) || 0) + 1);
    if (result === 'correct') row.correct_count = String((parseInt(row.correct_count, 10) || 0) + 1);
    row.last_seen_at = seenAt;
    row.last_result = result;
  }

  // All or nothing (spec 0002, Grading): picks equal to the answer as a set are
  // correct, any other pick is wrong, no pick is skipped. Both arrays sorted.
  function gradeResult(picks, answer) {
    if (!picks.length) return 'skipped';
    return picks.join(',') === answer.join(',') ? 'correct' : 'wrong';
  }

  // A new QuestionState row: unseen, box 0, empty due_at, no Bookmark.
  function blankStateRow(questionId) {
    var row = {};
    APP_TABS_[STATE_TAB_].forEach(function (name) { row[name] = ''; });
    row.question_id = questionId;
    row.box = '0';
    row.attempts = '0';
    row.correct_count = '0';
    row.bookmarked = 'FALSE';
    return row;
  }

  function refuseAnswer(message) {
    return { error: 'bad_answer', message: message };
  }

  // Grades one Review mode answer, appends its Attempts row and moves the
  // question through the Leitner boxes (spec 0002, Grading and spaced repetition).
  function answerReview(questionId, selected) {
    if (!Array.isArray(selected) || !selected.length) return refuseAnswer('Pick an answer first.');
    return withWriteLock(function () {
      var bankRows = adapter.tabs.read(QUESTIONS_TAB_).rows;
      var bankRow = activeRows(bankRows).filter(function (row) {
        return row.id === questionId;
      })[0];
      if (!bankRow) return refuseAnswer('This question is not an active question in the bank.');
      var answer = letterList(bankRow.answer);
      var picks = letterList(selected);
      if (picks.length !== selected.length) return refuseAnswer('A choice is picked twice.');
      var badLetter = picks.filter(function (letter) {
        return !/^[A-F]$/.test(letter) || isBlank(bankRow['choice_' + letter.toLowerCase()]);
      })[0];
      if (badLetter) return refuseAnswer('No choice ' + badLetter + ' on this question.');

      var result = gradeResult(picks, answer);
      var now = adapter.clock.now();
      var ctx = srContext(readSettings().exam_date);
      var stateRows = adapter.tabs.read(STATE_TAB_).rows;
      var row = statesById(stateRows)[questionId];
      if (!row) {
        row = blankStateRow(questionId);
        stateRows.push(row);
      }
      applyGraded(row, result, now, ctx.today, effectiveState(row, bankRow.answer, ctx));

      adapter.tabs.append(ATTEMPTS_TAB_, [{
        answered_at: now, question_id: questionId, mode: 'review', test_id: '', selected: picks.join(','),
        correct_answer: answer.join(','), result: result, question_updated_at: bankRow.updated_at, flagged: '',
      }]);
      adapter.tabs.rewrite(STATE_TAB_, stateRows);

      // This answer is now the last graded one, so the changed-answer rule is
      // clear for it: read the context again, with the new Attempts row in it.
      var after = srContext(readSettings().exam_date);
      return {
        result: result,
        correctAnswer: answer.join(','),
        state: stateForClient(row, effectiveState(row, bankRow.answer, after)),
        counts: countsOf(reviewLists(bankRows, stateRows, after)),
      };
    });
  }

  // ---- Bookmark and Note (spec 0002, Question card)

  var NOTE_MAX_ = 1000;

  // The QuestionState row of an active question, created unseen when absent
  // (box 0, empty due_at), with the bank row. Null when the question is not active.
  function markRow(stateRows, bankRows, questionId) {
    var bankRow = typeof questionId === 'string' ? activeRows(bankRows).filter(function (q) { return q.id === questionId; })[0] : null;
    if (!bankRow) return null;
    var row = statesById(stateRows)[questionId];
    if (!row) {
      row = blankStateRow(questionId);
      stateRows.push(row);
    }
    return { row: row, bankRow: bankRow };
  }

  // The reply of a mark call: the state row as the client gets it.
  function markState(mark) {
    return stateForClient(mark.row, effectiveState(mark.row, mark.bankRow.answer, srContext(readSettings().exam_date)));
  }

  function refuseMark(message) {
    return { error: 'bad_mark', message: message };
  }

  // Sets or clears the Bookmark at once. Returns the state row and the four
  // filter counts.
  function setBookmark(questionId, on) {
    if (typeof on !== 'boolean') return refuseMark('Bookmark on or off must be true or false.');
    return withWriteLock(function () {
      var bankRows = adapter.tabs.read(QUESTIONS_TAB_).rows;
      var stateRows = adapter.tabs.read(STATE_TAB_).rows;
      var mark = markRow(stateRows, bankRows, questionId);
      if (!mark) return refuseMark('This question is not an active question in the bank.');
      mark.row.bookmarked = on ? 'TRUE' : 'FALSE';
      adapter.tabs.rewrite(STATE_TAB_, stateRows);
      return {
        state: markState(mark),
        counts: countsOf(reviewLists(bankRows, stateRows, srContext(readSettings().exam_date))),
      };
    });
  }

  // Writes the note and note_updated_at, at most 1,000 characters. An empty
  // text clears the note.
  function saveNote(questionId, text) {
    if (typeof text !== 'string') return refuseMark('The note must be text.');
    return withWriteLock(function () {
      var bankRows = adapter.tabs.read(QUESTIONS_TAB_).rows;
      var stateRows = adapter.tabs.read(STATE_TAB_).rows;
      var mark = markRow(stateRows, bankRows, questionId);
      if (!mark) return refuseMark('This question is not an active question in the bank.');
      mark.row.note = text.slice(0, NOTE_MAX_);
      mark.row.note_updated_at = adapter.clock.now();
      adapter.tabs.rewrite(STATE_TAB_, stateRows);
      return { state: markState(mark) };
    });
  }

  // ---- Rebuild

  // Replays every Attempts row in sheet order through applyGraded, then
  // rewrites the six cache fields on every QuestionState row, adding rows for
  // questions that have none. bookmarked, note and note_updated_at stay.
  // Call under the write lock. Returns the QuestionState row count.
  function rebuildRows() {
    var replay = {};
    var order = [];
    var lastAnswer = {};
    adapter.tabs.read(ATTEMPTS_TAB_).rows.forEach(function (attempt) {
      var id = attempt.question_id;
      if (typeof id !== 'string' || id === '') return;
      if (attempt.result !== 'correct' && attempt.result !== 'wrong') return;
      var at = String(attempt.answered_at);
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(at)) return;
      var today = adapter.clock.dateOf(at);
      var answer = letterList(attempt.correct_answer).join(',');
      if (!replay[id]) {
        replay[id] = { box: '0', due_at: '', attempts: '0', correct_count: '0', last_seen_at: '', last_result: '' };
        order.push(id);
      }
      var work = replay[id];
      var eff;
      if (lastAnswer[id] !== undefined && lastAnswer[id] !== answer) eff = { box: 1, due: today };
      else if (boxOf(work) === 0) eff = { box: 0, due: '' };
      else eff = { box: boxOf(work), due: work.due_at };
      applyGraded(work, attempt.result, at, today, eff);
      lastAnswer[id] = answer;
    });

    var stateRows = adapter.tabs.read(STATE_TAB_).rows;
    var have = {};
    stateRows.forEach(function (row) { have[row.question_id] = true; });
    order.forEach(function (id) {
      if (have[id]) return;
      var row = {};
      APP_TABS_[STATE_TAB_].forEach(function (name) { row[name] = ''; });
      row.question_id = id;
      row.bookmarked = 'FALSE';
      stateRows.push(row);
    });
    var blank = { box: '0', due_at: '', attempts: '0', correct_count: '0', last_seen_at: '', last_result: '' };
    stateRows.forEach(function (row) {
      var source = replay[row.question_id] || blank;
      REBUILT_FIELDS_.forEach(function (name) { row[name] = source[name]; });
    });
    adapter.tabs.rewrite(STATE_TAB_, stateRows);
    return stateRows.length;
  }

  // The menu's "Rebuild study state". Returns the row count, or an error object.
  function rebuildState() {
    if (!adapter.tabs.exists(ATTEMPTS_TAB_) || !adapter.tabs.exists(STATE_TAB_)) {
      return { error: 'not_set_up', message: 'The app tabs are missing. Open the study app first.' };
    }
    return withWriteLock(rebuildRows);
  }

  var REVIEW_FILTERS_ = ['all', 'due', 'wrong', 'bookmarked'];

  // The four Review mode lists as arrays of question IDs, in the spec's orders
  // (Filter bar). Active questions only: retired and missing IDs are left out.
  // Ties in every order go to bank order.
  function reviewLists(bankRows, stateRows, ctx) {
    var bank = activeRows(bankRows);
    var states = statesById(stateRows);
    var unseen = [];
    var seen = [];
    var due = [];
    var wrong = [];
    var bookmarked = [];
    bank.forEach(function (row, i) {
      var state = states[row.id];
      if (state && String(state.bookmarked).toUpperCase() === 'TRUE') bookmarked.push(row.id);
      if (boxOf(state) === 0) {
        unseen.push(row.id);
        return;
      }
      var at = isEmptyCell(state.last_seen_at) ? '' : String(state.last_seen_at);
      seen.push({ id: row.id, at: at, order: i });
      var eff = effectiveState(state, row.answer, ctx);
      if (eff.due <= ctx.today) due.push({ id: row.id, due: eff.due, order: i });
      if (state.last_result === 'wrong') wrong.push({ id: row.id, at: at, order: i });
    });
    function ids(list) { return list.map(function (item) { return item.id; }); }
    seen.sort(function (a, b) { return a.at !== b.at ? (a.at < b.at ? -1 : 1) : a.order - b.order; });
    due.sort(function (a, b) { return a.due !== b.due ? (a.due < b.due ? -1 : 1) : a.order - b.order; });
    wrong.sort(function (a, b) { return a.at !== b.at ? (a.at > b.at ? -1 : 1) : a.order - b.order; });
    return { all: unseen.concat(ids(seen)), due: ids(due), wrong: ids(wrong), bookmarked: bookmarked };
  }

  function countsOf(lists) {
    return { all: lists.all.length, due: lists.due.length, wrong: lists.wrong.length, bookmarked: lists.bookmarked.length };
  }

  function reviewCounts(bankRows, examDate) {
    return countsOf(reviewLists(bankRows, adapter.tabs.read(STATE_TAB_).rows, srContext(examDate)));
  }

  function getReviewList(filter) {
    if (REVIEW_FILTERS_.indexOf(filter) < 0) return { error: 'unknown_filter', message: 'Unknown filter: ' + filter };
    var bankRows = adapter.tabs.read(QUESTIONS_TAB_).rows;
    var lists = reviewLists(bankRows, adapter.tabs.read(STATE_TAB_).rows, srContext(readSettings().exam_date));
    return { filter: filter, ids: lists[filter], counts: countsOf(lists) };
  }

  // ---- Mock Test: start, the pause screen read, discard (spec 0002, Mock Test)

  var MOCK_TESTS_TAB_ = 'MockTests';
  var MOCK_ITEMS_TAB_ = 'MockTestItems';

  // The in_progress MockTests row, or null. At most one exists.
  function unfinishedRow(rows) {
    return rows.filter(function (row) { return row.status === 'in_progress'; })[0] || null;
  }

  // Items of a test in position order.
  function itemsOf(testId) {
    return adapter.tabs.read(MOCK_ITEMS_TAB_).rows
      .filter(function (row) { return row.test_id === testId; })
      .sort(function (a, b) { return (parseInt(a.position, 10) || 0) - (parseInt(b.position, 10) || 0); });
  }

  function textOf(value) {
    return isEmptyCell(value) ? '' : String(value);
  }

  // The unfinished test as the pause screen and the home card get it. An item
  // is answered when it holds as many picks as its answer has letters.
  function testForClient(row, items, bankRows) {
    var answerLength = {};
    bankRows.forEach(function (q) { answerLength[q.id] = letterList(q.answer).length; });
    var answered = 0;
    var flagged = 0;
    var out = items.map(function (item) {
      var picks = letterList(item.selected).length;
      if (picks > 0 && picks === answerLength[item.question_id]) answered++;
      if (String(item.flagged).toUpperCase() === 'TRUE') flagged++;
      return {
        position: parseInt(item.position, 10), question_id: textOf(item.question_id), choice_order: textOf(item.choice_order),
        selected: textOf(item.selected), flagged: String(item.flagged).toUpperCase() === 'TRUE',
        question_updated_at: textOf(item.question_updated_at),
      };
    });
    return {
      test_id: textOf(row.test_id),
      started_at: textOf(row.started_at),
      started_on: /^\d{4}-\d{2}-\d{2}T/.test(textOf(row.started_at)) ? adapter.clock.dateOf(row.started_at) : '',
      question_count: parseInt(row.question_count, 10) || 0,
      minutes_allowed: parseInt(row.minutes_allowed, 10) || 0,
      seconds_left: parseInt(row.seconds_left, 10) || 0,
      answered: answered,
      flagged: flagged,
      items: out,
    };
  }

  // Sampler input: each active question with its Section, Subdomain and pool.
  function mockCandidates(bankRows, settings) {
    var ctx = srContext(settings.exam_date);
    var states = statesById(adapter.tabs.read(STATE_TAB_).rows);
    return activeRows(bankRows).map(function (q, i) {
      var state = states[q.id];
      var eff = state ? effectiveState(state, q.answer, ctx) : { box: 0, due: '' };
      var pool = eff.box === 0 ? 'unseen' : (eff.due <= ctx.today ? 'due' : 'weak');
      return {
        id: q.id, section: sectionOf(q), subdomain: textOf(q.subdomain).trim(), pool: pool,
        due: eff.due, box: eff.box, lastSeen: state && eff.box > 0 ? textOf(state.last_seen_at) : '', order: i,
      };
    });
  }

  // section_weights as {section: weight}, or null when empty.
  function parseWeights(text) {
    if (!text) return null;
    var out = {};
    text.split(',').forEach(function (pair) {
      var parts = pair.split(':');
      out[parts[0].trim()] = parts[1].trim();
    });
    return out;
  }

  // The letters of a bank row's filled choices, in order.
  function choiceLetters(q) {
    return ['A', 'B', 'C', 'D', 'E', 'F'].filter(function (l) { return !isBlank(q['choice_' + l.toLowerCase()]); });
  }

  function refuseStart(message) {
    return { error: 'bad_start', message: message };
  }

  // Samples a test, appends its MockTests row and writes its items. The count
  // and minutes apply to this test only: Settings is not written.
  function startMockTest(count, minutes) {
    var c = String(count);
    var m = String(minutes);
    if (!integerInRange(c, 1, 200)) return refuseStart('Question count: ' + FIELD_RULES_.mock_question_count);
    if (!integerInRange(m, 1, 600)) return refuseStart('Minutes: ' + FIELD_RULES_.mock_minutes);
    return withWriteLock(function () {
      var testRows = adapter.tabs.read(MOCK_TESTS_TAB_).rows;
      if (unfinishedRow(testRows)) {
        return { error: 'in_progress', message: 'A Mock Test is already unfinished. Resume or discard it first.' };
      }
      var bankRows = adapter.tabs.read(QUESTIONS_TAB_).rows;
      var settings = readSettings();
      var cands = mockCandidates(bankRows, settings);
      var subdomainOf = {};
      cands.forEach(function (q) { subdomainOf[q.id] = q.subdomain; });
      var weakness = subdomainWeakness_(adapter.tabs.read(ATTEMPTS_TAB_).rows, subdomainOf);
      var ids = sampleQuestions_(cands, parseWeights(settings.section_weights || ''), weakness, +c, adapter.random);
      if (!ids.length) return refuseStart('No active question has a Section weight above 0.');

      var byId = {};
      activeRows(bankRows).forEach(function (q) { byId[q.id] = q; });
      var now = adapter.clock.now();
      var testId = 't_' + now.replace(/[-:]/g, '');
      var row = {
        test_id: testId, status: 'in_progress', started_at: now, submitted_at: '', question_count: String(ids.length),
        minutes_allowed: String(+m), seconds_left: String(+m * 60), correct_count: '', score_pct: '',
      };
      var items = ids.map(function (id, i) {
        var q = byId[id];
        return {
          test_id: testId, position: String(i + 1), question_id: id, choice_order: shuffled_(choiceLetters(q), adapter.random).join(''),
          selected: '', flagged: 'FALSE', question_updated_at: textOf(q.updated_at),
        };
      });
      adapter.tabs.append(MOCK_TESTS_TAB_, [row]);
      adapter.tabs.rewrite(MOCK_ITEMS_TAB_, items);

      var notices = [];
      if (ids.length < +c) {
        notices.push('This test has ' + ids.length + ' questions, not ' + (+c) + ': the bank has only ' + ids.length + ' active questions.');
      }
      return { test: testForClient(row, items, bankRows), notices: notices };
    });
  }

  // ---- Re-import during a test (spec 0002, Re-import during a test)

  var DISCARDED_TEXT_ = 'The bank changed during the test and none of its questions are left, so the test was discarded.';

  // Whether the bank changed under the unfinished test `row`: an item whose
  // question is missing or not active, or whose updated_at moved. Read only.
  function needsReconcile(row) {
    var bankById = {};
    adapter.tabs.read(QUESTIONS_TAB_).rows.forEach(function (q) {
      if (typeof q.id === 'string' && !bankById[q.id]) bankById[q.id] = q;
    });
    return itemsOf(row.test_id).some(function (item) {
      var q = bankById[item.question_id];
      return !q || q.status !== 'active' || textOf(q.updated_at) !== textOf(item.question_updated_at);
    });
  }

  // The notice of a reconcile. `links` adds the colon and the list of reset
  // positions the client turns into links; the submit reply has no links.
  function reimportNotice(removed, remaining, resetPositions, links) {
    var text = 'The bank changed during this test.';
    if (removed) {
      text += ' ' + removed + (removed === 1 ? ' question was' : ' questions were') + ' removed, the test now has ' + remaining + '.';
    }
    if (resetPositions.length) {
      var k = resetPositions.length;
      text += ' ' + k + (k === 1 ? ' question was' : ' questions were') + ' edited and ' + (k === 1 ? 'its answer was' : 'their answers were') + ' cleared' + (links ? ':' : '.');
    }
    return links ? { text: text, links: resetPositions } : text;
  }

  // The reconcile. Call under the write lock with the unfinished test's
  // MockTests row. Drops items whose question is missing or retired and closes
  // positions up; resets items whose bank updated_at moved (answer cleared, new
  // choice_order and question_updated_at, place and Flag kept); sets
  // question_count; discards the test when nothing is left. Returns
  // {changed: false}, or {changed, removed, remaining, reset: [position],
  // discarded}.
  function reconcileTest(testRows, row) {
    var bankById = {};
    adapter.tabs.read(QUESTIONS_TAB_).rows.forEach(function (q) {
      if (typeof q.id === 'string' && !bankById[q.id]) bankById[q.id] = q;
    });
    var all = adapter.tabs.read(MOCK_ITEMS_TAB_).rows;
    var others = all.filter(function (item) { return item.test_id !== row.test_id; });
    var mine = all.filter(function (item) { return item.test_id === row.test_id; })
      .sort(function (a, b) { return (parseInt(a.position, 10) || 0) - (parseInt(b.position, 10) || 0); });
    var kept = [];
    var removed = 0;
    var resetItems = [];
    mine.forEach(function (item) {
      var q = bankById[item.question_id];
      if (!q || q.status !== 'active') {
        removed++;
        return;
      }
      if (textOf(q.updated_at) !== textOf(item.question_updated_at)) {
        item.selected = '';
        item.choice_order = shuffled_(choiceLetters(q), adapter.random).join('');
        item.question_updated_at = textOf(q.updated_at);
        resetItems.push(item);
      }
      kept.push(item);
    });
    if (!removed && !resetItems.length) return { changed: false };

    kept.forEach(function (item, i) { item.position = String(i + 1); });
    var discarded = kept.length === 0;
    row.question_count = String(kept.length);
    if (discarded) row.status = 'discarded';
    adapter.tabs.rewrite(MOCK_ITEMS_TAB_, others.concat(kept));
    adapter.tabs.rewrite(MOCK_TESTS_TAB_, testRows);
    return {
      changed: true, removed: removed, remaining: kept.length, discarded: discarded,
      reset: resetItems.map(function (item) { return parseInt(item.position, 10); }),
    };
  }

  // The current bank rows of the reset items, as the client keeps them.
  function resetBankRows(testId, positions) {
    var byId = {};
    adapter.tabs.read(QUESTIONS_TAB_).rows.forEach(function (q) { if (typeof q.id === 'string' && !byId[q.id]) byId[q.id] = q; });
    var at = {};
    itemsOf(testId).forEach(function (item) { at[parseInt(item.position, 10)] = item.question_id; });
    return positions.map(function (p) { return byId[at[p]]; }).filter(Boolean).map(bankRow);
  }

  // The unfinished test for the pause screen, or {test: null}. Reconciles
  // first. Reply: {test, notices, resetRows}; {test: null} with no test; or
  // {test: null, discarded: true, notices} when every item was dropped.
  function getMockTest() {
    var row = unfinishedRow(adapter.tabs.read(MOCK_TESTS_TAB_).rows);
    if (!row) return { test: null };
    var notices = [];
    var resetRows = [];
    if (needsReconcile(row)) {
      var done = withWriteLock(function () {
        var testRows = adapter.tabs.read(MOCK_TESTS_TAB_).rows;
        var current = unfinishedRow(testRows);
        if (!current) return { none: true };
        return { rec: reconcileTest(testRows, current), testId: current.test_id };
      });
      if (done.error) return done;
      if (done.none) return { test: null };
      if (done.rec.discarded) return { test: null, discarded: true, notices: [DISCARDED_TEXT_] };
      if (done.rec.changed) {
        notices.push(reimportNotice(done.rec.removed, done.rec.remaining, done.rec.reset, true));
        resetRows = resetBankRows(done.testId, done.rec.reset);
      }
      row = unfinishedRow(adapter.tabs.read(MOCK_TESTS_TAB_).rows);
    }
    return { test: testForClient(row, itemsOf(row.test_id), adapter.tabs.read(QUESTIONS_TAB_).rows), notices: notices, resetRows: resetRows };
  }

  // Checks one `changes` entry against its item. Returns the stored form
  // {selected, flagged} or null when the entry is bad.
  function checkedChange(change, item) {
    if (!change || typeof change !== 'object' || !Array.isArray(change.selected) || typeof change.flagged !== 'boolean') return null;
    var order = textOf(item.choice_order);
    var seen = {};
    for (var i = 0; i < change.selected.length; i++) {
      var letter = change.selected[i];
      if (typeof letter !== 'string' || order.indexOf(letter) < 0 || seen[letter]) return null;
      seen[letter] = true;
    }
    return { selected: change.selected.slice().sort().join(','), flagged: change.flagged ? 'TRUE' : 'FALSE' };
  }

  // Writes the changed items and the clock of the unfinished test `row`. Call
  // under the write lock. `changes` is [{position, selected: [stored letters],
  // flagged}]; every entry is checked before anything is written. The clock
  // only goes down. Returns null, or the bad_changes error with nothing written.
  function writeChanges(testRows, row, changes, secondsLeft) {
    if (!Array.isArray(changes)) return { error: 'bad_changes', message: 'The changes are not a list.' };
    var itemRows = adapter.tabs.read(MOCK_ITEMS_TAB_).rows;
    var byPosition = {};
    itemRows.forEach(function (item) {
      if (item.test_id === row.test_id) byPosition[parseInt(item.position, 10)] = item;
    });
    var checked = [];
    for (var i = 0; i < changes.length; i++) {
      var item = changes[i] && byPosition[changes[i].position];
      var stored = item ? checkedChange(changes[i], item) : null;
      if (!stored) return { error: 'bad_changes', message: 'Change ' + (i + 1) + ' does not match the test.' };
      checked.push({ item: item, stored: stored });
    }
    var itemsChanged = false;
    checked.forEach(function (c) {
      if (textOf(c.item.selected) !== c.stored.selected || String(c.item.flagged).toUpperCase() !== c.stored.flagged) {
        c.item.selected = c.stored.selected;
        c.item.flagged = c.stored.flagged;
        itemsChanged = true;
      }
    });
    if (itemsChanged) adapter.tabs.rewrite(MOCK_ITEMS_TAB_, itemRows);
    var sent = typeof secondsLeft === 'number' && isFinite(secondsLeft) ? Math.max(0, Math.floor(secondsLeft)) : null;
    var storedClock = parseInt(row.seconds_left, 10) || 0;
    if (sent !== null && sent < storedClock) {
      row.seconds_left = String(sent);
      adapter.tabs.rewrite(MOCK_TESTS_TAB_, testRows);
    }
    return null;
  }

  // Writes the changed items and the clock in one call (spec 0002, Saving).
  function saveMockTest(changes, secondsLeft) {
    return withWriteLock(function () {
      var testRows = adapter.tabs.read(MOCK_TESTS_TAB_).rows;
      var row = unfinishedRow(testRows);
      if (!row) return { error: 'not_unfinished', message: 'There is no unfinished Mock Test.' };
      return writeChanges(testRows, row, changes, secondsLeft) || { ok: true };
    });
  }

  // Sets the unfinished test to discarded and clears the items. No Attempts.
  function discardMockTest() {
    return withWriteLock(function () {
      var rows = adapter.tabs.read(MOCK_TESTS_TAB_).rows;
      var row = unfinishedRow(rows);
      if (!row) return { error: 'not_unfinished', message: 'There is no unfinished Mock Test.' };
      row.status = 'discarded';
      adapter.tabs.rewrite(MOCK_TESTS_TAB_, rows);
      adapter.tabs.clearBody(MOCK_ITEMS_TAB_);
      return { ok: true };
    });
  }

  // ---- Mock Test submit (spec 0002, Submit)

  // This test's Attempts rows in sheet order, which step 1 makes position order.
  function testAttempts(testId) {
    return adapter.tabs.read(ATTEMPTS_TAB_).rows.filter(function (a) { return a.mode === 'mock' && a.test_id === testId; });
  }

  // The SR context of a submit: the grading date is the date of answered_at,
  // and the changed-answer rule compares against the Attempts rows from before
  // this test, so a live submit and a recovery grade alike.
  function submitContext(examDate, answeredAt, testId) {
    var today = adapter.clock.dateOf(answeredAt);
    var before = adapter.tabs.read(ATTEMPTS_TAB_).rows.filter(function (a) { return a.test_id !== testId; });
    return { today: today, cap: capDate(examDate, today), lastAnswers: lastGradedAnswers(before) };
  }

  // correct ÷ count × 100, one decimal.
  function scorePct(correct, count) {
    return count > 0 ? (Math.round(correct * 1000 / count) / 10).toFixed(1) : '0.0';
  }

  // Submit steps 2 to 4, from the test's Attempts rows. Call under the write
  // lock. Step 2 skips a question whose last_seen_at already equals the test's
  // answered_at, so a second run changes nothing [G13]. Returns the question
  // IDs step 2 moved and the skipped count.
  function finishSubmit(testRows, row, attempts) {
    var answeredAt = textOf(attempts[0].answered_at);
    var ctx = submitContext(readSettings().exam_date, answeredAt, row.test_id);

    // Step 2: the Leitner table of ticket 33. A skipped row changes nothing.
    var stateRows = adapter.tabs.read(STATE_TAB_).rows;
    var byId = statesById(stateRows);
    var changed = [];
    attempts.forEach(function (a) {
      if (a.result !== 'correct' && a.result !== 'wrong') return;
      var id = a.question_id;
      var state = byId[id];
      if (state && textOf(state.last_seen_at) === answeredAt) return;
      if (!state) {
        state = blankStateRow(id);
        stateRows.push(state);
        byId[id] = state;
      }
      applyGraded(state, a.result, answeredAt, ctx.today, effectiveState(state, a.correct_answer, ctx));
      changed.push(id);
    });
    if (changed.length) adapter.tabs.rewrite(STATE_TAB_, stateRows);

    // Step 3: the MockTests row. seconds_left was stored with the changes.
    var correct = attempts.filter(function (a) { return a.result === 'correct'; }).length;
    row.status = 'submitted';
    row.submitted_at = answeredAt;
    row.correct_count = String(correct);
    row.score_pct = scorePct(correct, parseInt(row.question_count, 10) || 0);
    adapter.tabs.rewrite(MOCK_TESTS_TAB_, testRows);

    // Step 4: clear MockTestItems.
    adapter.tabs.rewrite(MOCK_ITEMS_TAB_, adapter.tabs.read(MOCK_ITEMS_TAB_).rows.filter(function (item) {
      return item.test_id !== row.test_id;
    }));
    return { changed: changed, skipped: attempts.filter(function (a) { return a.result === 'skipped'; }).length };
  }

  // The submitted MockTests row as the results header gets it.
  function submittedForClient(row, skipped) {
    return {
      test_id: textOf(row.test_id),
      submitted_at: textOf(row.submitted_at),
      submitted_on: adapter.clock.dateOf(row.submitted_at),
      question_count: parseInt(row.question_count, 10) || 0,
      minutes_allowed: parseInt(row.minutes_allowed, 10) || 0,
      seconds_left: parseInt(row.seconds_left, 10) || 0,
      correct_count: parseInt(row.correct_count, 10) || 0,
      score_pct: textOf(row.score_pct),
      skipped: skipped,
    };
  }

  // Spec 0002, History screen: the submitted MockTests rows, newest first. A
  // discarded or unfinished test has no score and is left out. Ties on
  // submitted_at put the later row first. Every value comes from the row.
  function getHistory() {
    var rows = adapter.tabs.read(MOCK_TESTS_TAB_).rows;
    var tests = [];
    rows.forEach(function (row, index) {
      if (row.status !== 'submitted') return;
      var test = submittedForClient(row, 0);
      delete test.skipped;
      test.index = index;
      tests.push(test);
    });
    tests.sort(function (a, b) {
      if (a.submitted_at !== b.submitted_at) return a.submitted_at < b.submitted_at ? 1 : -1;
      return b.index - a.index;
    });
    tests.forEach(function (test) { delete test.index; });
    return { tests: tests };
  }

  // Step 1: one Attempts row per item, in position order, graded against the
  // bank row. The reconcile has already dropped missing and retired items.
  function appendTestAttempts(row) {
    var bankById = {};
    adapter.tabs.read(QUESTIONS_TAB_).rows.forEach(function (q) {
      if (typeof q.id === 'string' && !bankById[q.id]) bankById[q.id] = q;
    });
    var now = adapter.clock.now();
    var attempts = itemsOf(row.test_id).map(function (item) {
      var q = bankById[item.question_id];
      var answer = q ? letterList(q.answer) : [];
      var picks = letterList(item.selected);
      return {
        answered_at: now, question_id: textOf(item.question_id), mode: 'mock', test_id: textOf(row.test_id),
        selected: picks.join(','), correct_answer: answer.join(','), result: gradeResult(picks, answer),
        question_updated_at: q ? textOf(q.updated_at) : '',
        flagged: String(item.flagged).toUpperCase() === 'TRUE' ? 'TRUE' : 'FALSE',
      };
    });
    adapter.tabs.append(ATTEMPTS_TAB_, attempts);
    return attempts;
  }

  // Submits the unfinished test under one lock: writes the sent changes and
  // the clock (0 when `timedOut`), then the four steps in the spec's order. A
  // test whose step 1 already ran finishes from step 2 and appends nothing.
  function submitMockTest(changes, secondsLeft, timedOut) {
    return withWriteLock(function () {
      var testRows = adapter.tabs.read(MOCK_TESTS_TAB_).rows;
      var row = unfinishedRow(testRows);
      if (!row) return { error: 'not_unfinished', message: 'There is no unfinished Mock Test.' };
      var attempts = testAttempts(row.test_id);
      var notices = [];
      var resetRows = [];
      if (!attempts.length) {
        var bad = writeChanges(testRows, row, changes, timedOut === true ? 0 : secondsLeft);
        if (bad) return bad;
        // The re-import reconcile, after the sent changes, before step 1.
        var rec = reconcileTest(testRows, row);
        if (rec.changed) {
          if (rec.discarded) return { discarded: true, notices: [DISCARDED_TEXT_] };
          resetRows = resetBankRows(row.test_id, rec.reset);
          // A manual submit that dropped or reset an item submits nothing.
          if (timedOut !== true) {
            return {
              unfinished: testForClient(row, itemsOf(row.test_id), adapter.tabs.read(QUESTIONS_TAB_).rows),
              notices: [reimportNotice(rec.removed, rec.remaining, rec.reset, true)],
              resetRows: resetRows,
            };
          }
          // At zero seconds it goes through: a reset item has no answer, so it is skipped.
          notices.push(reimportNotice(rec.removed, rec.remaining, rec.reset, false));
        }
        attempts = appendTestAttempts(row);
      }
      var finished = finishSubmit(testRows, row, attempts);

      var bankRows = adapter.tabs.read(QUESTIONS_TAB_).rows;
      var answers = {};
      bankRows.forEach(function (q) { answers[q.id] = q.answer; });
      var after = srContext(readSettings().exam_date);
      var stateRows = adapter.tabs.read(STATE_TAB_).rows;
      var byId = statesById(stateRows);
      var states = {};
      finished.changed.forEach(function (id) { states[id] = stateForClient(byId[id], effectiveState(byId[id], answers[id], after)); });
      var reply = {
        test_id: textOf(row.test_id),
        test: submittedForClient(row, finished.skipped),
        states: states,
        counts: countsOf(reviewLists(bankRows, stateRows, after)),
      };
      if (notices.length) {
        reply.notices = notices;
        reply.resetRows = resetRows;
      }
      return reply;
    });
  }

  // ---- Results screen (spec 0002, Results screen)

  // [section, sub] sort key of a Subdomain number such as "2.10".
  function subdomainKey(text) {
    return String(text).split('.').map(function (part) { return parseInt(part, 10) || 0; });
  }

  function compareKeys(a, b) {
    for (var i = 0; i < Math.max(a.length, b.length); i++) {
      var d = (a[i] || 0) - (b[i] || 0);
      if (d !== 0) return d;
    }
    return 0;
  }

  function tally(correct, count) {
    return { correct: correct, count: count, pct: scorePct(correct, count) };
  }

  // The Score by Section breakdown from the test's attempt rows, each marked
  // with its bank state. Questions group by their Subdomain in Questions today;
  // a missing ID goes to notInBank. The Total is the sum of every row, so it
  // equals the stored score.
  function breakdownOf(attempts, bankById) {
    var sections = {};
    var missing = { correct: 0, count: 0 };
    var total = { correct: 0, count: 0 };
    attempts.forEach(function (a) {
      var right = a.result === 'correct' ? 1 : 0;
      total.correct += right;
      total.count += 1;
      var q = bankById[a.question_id];
      if (!q) {
        missing.correct += right;
        missing.count += 1;
        return;
      }
      var sectionNo = sectionOf(q);
      var sec = sections[sectionNo] || (sections[sectionNo] = { section: sectionNo, correct: 0, count: 0, subs: {} });
      sec.correct += right;
      sec.count += 1;
      var sub = sec.subs[q.subdomain] || (sec.subs[q.subdomain] = { subdomain: textOf(q.subdomain), title: textOf(q.subdomain_title), correct: 0, count: 0 });
      sub.correct += right;
      sub.count += 1;
    });
    var rows = Object.keys(sections).sort(function (a, b) { return compareKeys(subdomainKey(a), subdomainKey(b)); }).map(function (key) {
      var sec = sections[key];
      var subs = Object.keys(sec.subs).sort(function (a, b) { return compareKeys(subdomainKey(a), subdomainKey(b)); }).map(function (k) {
        var sub = sec.subs[k];
        return { subdomain: sub.subdomain, title: sub.title, correct: sub.correct, count: sub.count, pct: scorePct(sub.correct, sub.count) };
      });
      return { section: sec.section, label: sec.section === '' ? 'No Section' : 'Section ' + sec.section, correct: sec.correct, count: sec.count, pct: scorePct(sec.correct, sec.count), subdomains: subs };
    });
    return {
      sections: rows,
      notInBank: missing.count > 0 ? tally(missing.correct, missing.count) : null,
      total: tally(total.correct, total.count),
    };
  }

  // A submitted test rebuilt from its MockTests row and its Attempts rows.
  // Read-only: nothing is written. Each attempt carries `bank`: 'ok', 'retired'
  // or 'missing', and `edited` when the bank row's updated_at differs from the
  // one graded.
  function getResults(testId) {
    var row = adapter.tabs.read(MOCK_TESTS_TAB_).rows.filter(function (t) { return t.test_id === testId && t.status === 'submitted'; })[0];
    if (!row) return { error: 'no_test', message: 'This Mock Test has no results.' };
    var bankById = {};
    adapter.tabs.read(QUESTIONS_TAB_).rows.forEach(function (q) {
      if (typeof q.id === 'string' && q.id !== '' && !bankById[q.id]) bankById[q.id] = q;
    });
    var attempts = testAttempts(testId).map(function (a, i) {
      var q = bankById[a.question_id];
      return {
        position: i + 1,
        question_id: textOf(a.question_id),
        selected: textOf(a.selected),
        correct_answer: textOf(a.correct_answer),
        result: textOf(a.result),
        question_updated_at: textOf(a.question_updated_at),
        flagged: String(a.flagged).toUpperCase() === 'TRUE',
        bank: !q ? 'missing' : q.status === 'retired' ? 'retired' : 'ok',
        edited: !!q && textOf(q.updated_at) !== textOf(a.question_updated_at),
      };
    });
    var skipped = attempts.filter(function (a) { return a.result === 'skipped'; }).length;
    return { test: submittedForClient(row, skipped), attempts: attempts, breakdown: breakdownOf(attempts, bankById) };
  }

  // Load step 6: each test that has Attempts rows and is not submitted
  // finishes from step 2, appending nothing. Takes the lock only when one
  // needs it. Returns null, or the busy error.
  function finishHalfSubmitted() {
    function halfSubmittedTests() {
      var hasAttempts = {};
      adapter.tabs.read(ATTEMPTS_TAB_).rows.forEach(function (a) { if (a.mode === 'mock') hasAttempts[a.test_id] = true; });
      var testRows = adapter.tabs.read(MOCK_TESTS_TAB_).rows;
      return { testRows: testRows, rows: testRows.filter(function (t) { return t.status !== 'submitted' && hasAttempts[t.test_id]; }) };
    }
    if (!halfSubmittedTests().rows.length) return null;
    return withWriteLock(function () {
      var found = halfSubmittedTests();
      found.rows.forEach(function (row) { finishSubmit(found.testRows, row, testAttempts(row.test_id)); });
      return null;
    });
  }

  // The home card's summary of the unfinished test, or null.
  function mockSummary(bankRows) {
    var row = unfinishedRow(adapter.tabs.read(MOCK_TESTS_TAB_).rows);
    if (!row) return null;
    var test = testForClient(row, itemsOf(row.test_id), bankRows);
    return { answered: test.answered, question_count: test.question_count, seconds_left: test.seconds_left, started_on: test.started_on };
  }

  return {
    load: load, saveSettings: saveSettings, getReviewList: getReviewList, answerReview: answerReview,
    setBookmark: setBookmark, saveNote: saveNote, saveReport: saveReport, getReports: getReports, rebuildState: rebuildState,
    startMockTest: startMockTest, getMockTest: getMockTest, saveMockTest: saveMockTest, discardMockTest: discardMockTest,
    submitMockTest: submitMockTest, getResults: getResults, getHistory: getHistory,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { makeServer_: makeServer_, IMPORT_STEPS_: IMPORT_STEPS_ };
}
