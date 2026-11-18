const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { fixtureBank } = require('./bank-fixture.js');

// Load the client file the way the page does, minus the script tags.
const source = fs.readFileSync(path.join(__dirname, '..', 'client', 'prompt.html'), 'utf8');
assert.equal((source.match(/<script>/g) || []).length, 1);
const body = source.replace(/<\/?script>/g, '');
const buildPrompt = new Function(`${body}; return buildPrompt;`)();

const bank = fixtureBank();
function row(id) {
  const r = bank.slice(1).find((x) => x[0] === id);
  const o = {};
  bank[0].forEach((h, i) => { o[h] = r[i]; });
  return o;
}
const SINGLE = row('q_042896dc1966'); // answer B, four choices
const UNCERTAIN = row('q_c1db13ab836d');
const SIX = row('q_bf7be128c7d4'); // six choices

const SENTENCES = {
  Beginner: 'I am new to Google Cloud ML. Define each service you mention in one sentence and use plain words.',
  Intermediate: 'I know the core Google Cloud ML services. Skip definitions. Focus on why each choice fits or fails.',
  Expert: 'Be brief. Focus on edge cases, trade-offs and limits that decide between the close choices.',
};

const wrong = { picked: ['A'], result: 'wrong' };

test('each level fills its line and changes nothing else', () => {
  const texts = {};
  for (const level of Object.keys(SENTENCES)) {
    texts[level] = buildPrompt(SINGLE, level, 'Professional ML Engineer', wrong);
    assert.ok(texts[level].startsWith('I am studying for the Professional ML Engineer exam. Explain this practice question.\n\nLevel: '));
    assert.ok(texts[level].includes(`\nLevel: ${level}. ${SENTENCES[level]}\n`));
  }
  const strip = (t) => t.split('\n').filter((l) => !l.startsWith('Level: ')).join('\n');
  assert.equal(strip(texts.Beginner), strip(texts.Intermediate));
  assert.equal(strip(texts.Expert), strip(texts.Intermediate));
});

test('the template holds the question fields in order', () => {
  const t = buildPrompt(SINGLE, 'Intermediate', 'Professional ML Engineer', wrong);
  const at = (s) => { const i = t.indexOf(s); assert.ok(i >= 0, s); return i; };
  const order = [
    'Subdomain ' + SINGLE.subdomain + ': ' + SINGLE.subdomain_title,
    'Question:\n' + SINGLE.question,
    'Choices:\nA) ' + SINGLE.choice_a,
    'B) ' + SINGLE.choice_b,
    'Stated correct answer: B\nMy answer: A (wrong)',
    'Explanations I already read:\nA) ' + SINGLE.explanation_a,
    'Do this:\n1. Do not repeat the explanations above. Go deeper.',
  ];
  let last = -1;
  for (const s of order) { const i = at(s); assert.ok(i > last, s); last = i; }
  assert.ok(t.endsWith('6. End with one rule of thumb I can reuse on similar questions.'));
  assert.ok(!t.includes('Sources disagree'));
  assert.ok(!t.includes('E) '));
});

test('the Sources disagree line shows only on an Uncertain answer', () => {
  const t = buildPrompt(UNCERTAIN, 'Intermediate', 'X', { picked: ['A'], result: 'correct' });
  assert.ok(t.includes('My answer: A (correct)\nSources disagree on this answer. Check it first.\n\nExplanations I already read:'));
  assert.ok(!buildPrompt(SINGLE, 'Intermediate', 'X', wrong).includes('Sources disagree'));
});

test('a skipped answer reads none (skipped)', () => {
  const t = buildPrompt(SINGLE, 'Intermediate', 'X', { picked: [], result: 'skipped' });
  assert.ok(t.includes('Stated correct answer: B\nMy answer: none (skipped)\n'));
});

test('a multi-pick answer lists the letters in order', () => {
  const multi = row('q_dba0082ec68e'); // A,C
  const t = buildPrompt(multi, 'Intermediate', 'X', { picked: ['C', 'A'], result: 'correct' });
  assert.ok(t.includes('Stated correct answer: A, C\nMy answer: A, C (correct)'));
});

test('a six-choice question lists all six choices and explanations', () => {
  const t = buildPrompt(SIX, 'Expert', 'X', { picked: ['A'], result: 'wrong' });
  for (const l of ['A', 'B', 'C', 'D', 'E', 'F']) {
    assert.ok(t.includes(`\n${l}) ${SIX['choice_' + l.toLowerCase()]}`), 'choice ' + l);
    assert.ok(t.includes(`\n${l}) ${SIX['explanation_' + l.toLowerCase()]}`), 'explanation ' + l);
  }
});

test('the user note is not a builder input', () => {
  assert.equal(buildPrompt.length, 4);
  const t = buildPrompt({ ...SINGLE, note: 'MY PRIVATE NOTE' }, 'Intermediate', 'X', wrong);
  assert.ok(!t.includes('MY PRIVATE NOTE'));
});
