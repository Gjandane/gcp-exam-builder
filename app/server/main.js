// Apps Script entry points: the web page, the sheet menu, and the server
// interface bound to the Apps Script adapter. Names ending in _ are hidden
// from google.script.run.

function doGet() {
  // Save the URL this page was served from, for the menu's "Open study app".
  try {
    var url = ScriptApp.getService().getUrl();
    if (url) PropertiesService.getScriptProperties().setProperty('web_app_url', url);
  } catch (e) { /* the page still renders */ }
  return HtmlService.createTemplateFromFile('client/index').evaluate()
    .setTitle('Study app')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

// HtmlService include for client/*.html parts.
function include_(name) {
  return HtmlService.createHtmlOutputFromFile(name).getContent();
}

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Study app')
    .addItem('Open study app', 'openStudyApp')
    .addItem('Import bank', 'showImportSteps')
    .addItem('Rebuild study state', 'rebuildStudyState')
    .addToUi();
}

// Menu item: a dialog with the import steps, the same constant the app shows.
function showImportSteps() {
  var html = HtmlService.createHtmlOutput(
    '<div style="font:14px Arial,sans-serif;white-space:pre-line">' + escapeHtml_(IMPORT_STEPS_) + '</div>'
  ).setWidth(520).setHeight(220);
  SpreadsheetApp.getUi().showModalDialog(html, 'Import bank');
}

// Menu item: a small dialog linking to the web app, since a menu item cannot
// open a full page itself.
function openStudyApp() {
  var url = appsScriptAdapter_().urls.webApp();
  var body = url
    ? '<p><a href="' + escapeHtml_(url) + '" target="_blank" rel="noopener">Open the study app in a new tab</a></p>'
    : '<p>Open the web app once from its URL first. See the README, Part 2, step 4.</p>';
  var html = HtmlService.createHtmlOutput(
    '<div style="font:14px Arial,sans-serif">' + body + '</div>'
  ).setWidth(360).setHeight(100);
  SpreadsheetApp.getUi().showModalDialog(html, 'Study app');
}

// Menu item: after a confirm, replays Attempts into QuestionState (spec 0002, Rebuild).
function rebuildStudyState() {
  var ui = SpreadsheetApp.getUi();
  var answer = ui.alert(
    'Rebuild study state',
    'This rewrites the boxes, due dates and counters of every question from the Attempts tab. Bookmarks and notes are kept. Continue?',
    ui.ButtonSet.OK_CANCEL
  );
  if (answer !== ui.Button.OK) return;
  var result = server_().rebuildState();
  ui.alert(typeof result === 'number'
    ? 'Rebuilt the study state of ' + result + ' questions.'
    : result.message);
}

function escapeHtml_(text) {
  return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function server_() {
  return makeServer_(appsScriptAdapter_());
}

function load() {
  return server_().load();
}

function saveSettings(values) {
  return server_().saveSettings(values);
}

function getReviewList(filter) {
  return server_().getReviewList(filter);
}

function answerReview(questionId, selected) {
  return server_().answerReview(questionId, selected);
}

function setBookmark(questionId, on) {
  return server_().setBookmark(questionId, on);
}

function saveNote(questionId, text) {
  return server_().saveNote(questionId, text);
}

function saveReport(questionId, note) {
  return server_().saveReport(questionId, note);
}

function getReports(questionId) {
  return server_().getReports(questionId);
}

function startMockTest(count, minutes) {
  return server_().startMockTest(count, minutes);
}

function getMockTest() {
  return server_().getMockTest();
}

function saveMockTest(changes, secondsLeft) {
  return server_().saveMockTest(changes, secondsLeft);
}

function discardMockTest() {
  return server_().discardMockTest();
}

function submitMockTest(changes, secondsLeft, timedOut) {
  return server_().submitMockTest(changes, secondsLeft, timedOut);
}

function getResults(testId) {
  return server_().getResults(testId);
}

function getHistory() {
  return server_().getHistory();
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { doGet: doGet, onOpen: onOpen, openStudyApp: openStudyApp, showImportSteps: showImportSteps, rebuildStudyState: rebuildStudyState, load: load, saveSettings: saveSettings, getReviewList: getReviewList, answerReview: answerReview, setBookmark: setBookmark, saveNote: saveNote, saveReport: saveReport, getReports: getReports, startMockTest: startMockTest, getMockTest: getMockTest, saveMockTest: saveMockTest, discardMockTest: discardMockTest, submitMockTest: submitMockTest, getResults: getResults, getHistory: getHistory };
}
