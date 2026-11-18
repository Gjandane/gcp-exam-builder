// The Mock Test sampler, spec 0002 Sampler. Pure functions: the server reads
// the sheet and hands in candidates, weights and weakness; every random
// number comes from the `random` function it passes (adapter.random).

var BUCKET_SHARE_TENTHS_ = { due: 4, unseen: 3, weak: 3 };
// Rounding ties and spill go in this order: due, then weak-fill, then unseen.
var BUCKET_ORDER_ = ['due', 'weak', 'unseen'];
var WEAKNESS_WINDOW_ = 30;
var WEAKNESS_FLOOR_ = 0.1;

// Fisher-Yates on a copy.
function shuffled_(list, random) {
  var out = list.slice();
  for (var i = out.length - 1; i > 0; i--) {
    var j = Math.floor(random() * (i + 1));
    var t = out[i];
    out[i] = out[j];
    out[j] = t;
  }
  return out;
}

// Weakness per Subdomain: 1 - (correct + 2) / (attempts + 4) over its last 30
// non-skipped Attempts rows in sheet order, both modes. `subdomainOf` maps an
// active question ID to its Subdomain; other IDs (missing, retired) are left out.
// A Subdomain with no attempts is absent here and scores 0.5.
function subdomainWeakness_(attemptRows, subdomainOf) {
  var recent = {};
  attemptRows.forEach(function (row) {
    if (row.result !== 'correct' && row.result !== 'wrong') return;
    var sub = subdomainOf[row.question_id];
    if (sub === undefined) return;
    (recent[sub] = recent[sub] || []).push(row.result === 'correct');
  });
  var out = {};
  Object.keys(recent).forEach(function (sub) {
    var last = recent[sub].slice(-WEAKNESS_WINDOW_);
    var correct = last.filter(Boolean).length;
    out[sub] = 1 - (correct + 2) / (last.length + 4);
  });
  return out;
}

// Splits `total` across `keys` by integer `weights` with largest remainder.
// `before(a, b)` orders a remainder tie. Returns {key: count}.
function largestRemainder_(total, keys, weights, before) {
  var sum = 0;
  keys.forEach(function (k) { sum += weights[k]; });
  var out = {};
  var rem = {};
  var placed = 0;
  keys.forEach(function (k) {
    out[k] = sum > 0 ? Math.floor(total * weights[k] / sum) : 0;
    rem[k] = sum > 0 ? (total * weights[k]) % sum : 0;
    placed += out[k];
  });
  var order = keys.slice().sort(function (a, b) {
    if (rem[a] !== rem[b]) return rem[b] - rem[a];
    return before(a, b);
  });
  for (var i = 0; i < total - placed && sum > 0; i++) out[order[i % order.length]]++;
  return out;
}

// Weights as integers, so remainders compare exactly: each times 10 to the
// power of the most decimal places among them.
function integerWeights_(weights) {
  var places = 0;
  Object.keys(weights).forEach(function (k) {
    var m = /\.(\d+)$/.exec(String(weights[k]));
    if (m) places = Math.max(places, m[1].length);
  });
  var scale = Math.pow(10, places);
  var out = {};
  Object.keys(weights).forEach(function (k) { out[k] = Math.round(parseFloat(weights[k]) * scale); });
  return out;
}

// Step 1: the Section split. `sections` is in a fixed order; `weights` integer;
// `have[n]` the candidates of Section n. Shortfall goes round again, by weight,
// to the Sections with candidates left.
function splitSections_(count, sections, weights, have) {
  var taken = {};
  sections.forEach(function (n) { taken[n] = 0; });
  var before = function (a, b) {
    if (weights[a] !== weights[b]) return weights[b] - weights[a];
    return parseInt(a, 10) - parseInt(b, 10);
  };
  var open = count;
  var eligible = sections.filter(function (n) { return weights[n] > 0; });
  while (open > 0 && eligible.length) {
    var shares = largestRemainder_(open, eligible, weights, before);
    open = 0;
    eligible.forEach(function (n) {
      var take = Math.min(shares[n], have[n] - taken[n]);
      taken[n] += take;
      open += shares[n] - take;
    });
    eligible = eligible.filter(function (n) { return have[n] - taken[n] > 0; });
  }
  return taken;
}

// Step 2: the 40/30/30 bucket split of one Section share.
function splitBuckets_(share) {
  var rank = { due: 0, weak: 1, unseen: 2 };
  return largestRemainder_(share, BUCKET_ORDER_, BUCKET_SHARE_TENTHS_, function (a, b) { return rank[a] - rank[b]; });
}

function compareText_(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

// Pick order inside a Subdomain, ties in bank order. Unseen is shuffled once.
function pickOrder_(pool, list, random) {
  if (pool === 'unseen') return shuffled_(list, random);
  return list.slice().sort(function (a, b) {
    var c = pool === 'due' ? compareText_(a.due, b.due) : (a.box - b.box) || compareText_(a.lastSeen, b.lastSeen);
    return c || a.order - b.order;
  });
}

// Steps 2 to 4 for one Section. `cands` are its candidates in bank order.
function sampleSection_(cands, share, weakness, random) {
  var subs = [];
  var queues = { due: {}, weak: {}, unseen: {} };
  cands.forEach(function (c) {
    if (subs.indexOf(c.subdomain) < 0) subs.push(c.subdomain);
    (queues[c.pool][c.subdomain] = queues[c.pool][c.subdomain] || []).push(c);
  });
  BUCKET_ORDER_.forEach(function (pool) {
    Object.keys(queues[pool]).forEach(function (sub) { queues[pool][sub] = pickOrder_(pool, queues[pool][sub], random); });
  });
  var picked = [];
  var used = {};

  // Step 3: one draw. A Subdomain with candidates left in the pool, weighted
  // by weakness with a floor; then its first question in pick order.
  function draw(pool) {
    var live = subs.filter(function (s) { return queues[pool][s] && queues[pool][s].length; });
    if (!live.length) return false;
    var w = live.map(function (s) {
      return Math.max(weakness[s] === undefined ? 0.5 : weakness[s], WEAKNESS_FLOOR_);
    });
    var sum = w.reduce(function (a, b) { return a + b; }, 0);
    var x = random() * sum;
    var i = 0;
    while (i < live.length - 1 && x >= w[i]) { x -= w[i]; i++; }
    var c = queues[pool][live[i]].shift();
    used[c.id] = true;
    picked.push(c.id);
    return true;
  }

  var quota = splitBuckets_(share);
  var open = 0;
  BUCKET_ORDER_.forEach(function (pool) {
    for (var k = 0; k < quota[pool]; k++) if (!draw(pool)) open++;
  });
  // Step 4: spill, due then weak-fill then unseen, then any candidate left by
  // oldest last_seen_at (unseen '' sorts first), ties in bank order.
  BUCKET_ORDER_.forEach(function (pool) {
    while (open > 0 && draw(pool)) open--;
  });
  if (open > 0) {
    cands.filter(function (c) { return !used[c.id]; })
      .sort(function (a, b) { return compareText_(a.lastSeen, b.lastSeen) || a.order - b.order; })
      .slice(0, open)
      .forEach(function (c) { picked.push(c.id); });
  }
  return picked;
}

// The whole sampler. `candidates`: active questions in bank order, each
// {id, section, subdomain, pool: 'due'|'weak'|'unseen', due, box, lastSeen, order}.
// `weights`: {section: number}, from section_weights, or null for the bank's
// own proportions. Returns the question IDs in test order (step 5's question
// shuffle; the caller shuffles each question's choices).
function sampleQuestions_(candidates, weights, weakness, count, random) {
  var sections = [];
  var bySection = {};
  candidates.forEach(function (c) {
    if (!bySection[c.section]) { bySection[c.section] = []; sections.push(c.section); }
    bySection[c.section].push(c);
  });
  var raw = {};
  if (weights) {
    Object.keys(weights).forEach(function (n) {
      raw[n] = weights[n];
      if (!bySection[n]) { bySection[n] = []; sections.push(n); }
    });
  } else {
    sections.forEach(function (n) { raw[n] = bySection[n].length; });
  }
  sections.forEach(function (n) { if (raw[n] === undefined) raw[n] = 0; });
  sections.sort(function (a, b) { return parseInt(a, 10) - parseInt(b, 10); });
  var have = {};
  sections.forEach(function (n) { have[n] = bySection[n].length; });
  var shares = splitSections_(count, sections, integerWeights_(raw), have);
  var ids = [];
  sections.forEach(function (n) {
    if (shares[n] > 0) ids = ids.concat(sampleSection_(bySection[n], shares[n], weakness, random));
  });
  return shuffled_(ids, random);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    shuffled_: shuffled_, subdomainWeakness_: subdomainWeakness_, sampleQuestions_: sampleQuestions_,
  };
}
