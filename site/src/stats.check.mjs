// Known-answer self-check, run by "npm run build" before vite: node src/stats.check.mjs
// Every browser computation is reproduced against the repo's own generated files.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { wilson, shortfallCI, staleCI, staleSlots, c2, c2Agrees, h6, pick, parseVerdicts, parseC2, parsePrereg, parseLimits } from './stats.js';

const root = new URL('../../', import.meta.url);
const read = (p) => fs.readFileSync(new URL(p, root), 'utf8');
const results = JSON.parse(read('results/cells.json'));
const env = JSON.parse(read('results/env.json'));
const resultsMd = read('RESULTS.md');
const pre = parsePrereg(read('HYPOTHESES.md'));
const f3 = (x) => x.toFixed(3);

// 1. Wilson intervals reproduce the generated RESULTS.md columns, row by row.
assert.deepEqual(wilson(0.5, 100).map((x) => +x.toFixed(4)), [0.4038, 0.5962]);
for (const e of [...results.cells, ...results.trap]) {
  const [lo, hi] = shortfallCI(e);
  const row = `| ${e.backend} | ${e.arm} | ${f3(e.selectivity)} | ${e.n_queries} x ${e.reps} | ${f3(e.recall10)} | ${f3(e.shortfall_rate)} | ${f3(lo)} to ${f3(hi)} |`;
  assert.ok(resultsMd.includes(row), `shortfall CI row missing: ${row}`);
  const count = e.shortfall_rate * e.n_queries;
  assert.ok(Math.abs(count - Math.round(count)) < 1e-6, 'shortfall must be a whole number of queries');
}
for (const e of results.churn) {
  const [lo, hi] = staleCI(e);
  const cellText = `| ${f3(e.stale_rate)} | ${f3(lo)} to ${f3(hi)} (${staleSlots(e)}) |`;
  assert.ok(resultsMd.includes(cellText), `stale CI missing for ${e.backend} ${e.arm} ${e.cell}: ${cellText}`);
}

// 2. C2 calculator reproduces the generated C2 check (4.75 agree, 0.42 disagree).
const c2md = parseC2(resultsMd);
const trap = ['trap_tenant_t2', 'trap_tenant_t5'].map((c) => results.trap.find((t) => t.cell === c));
trap.forEach((t, i) => {
  const r = c2(pre.efDefault, t.selectivity, env.k);
  assert.equal(+r.predicted.toFixed(2), c2md[i].predicted, `C2 prediction ${t.cell}`);
  assert.equal(+t.mean_returned.toFixed(2), c2md[i].measured, `C2 measured ${t.cell}`);
});
assert.equal(c2Agrees(trap[0].mean_returned, c2(pre.efDefault, trap[0].selectivity, env.k).predicted, env.k), true);
assert.equal(c2Agrees(trap[1].mean_returned, c2(pre.efDefault, trap[1].selectivity, env.k).predicted, env.k), false);
assert.equal(c2(400, 1, 10).expected, 10, 'expected matches are capped at k');

// 3. H6 re-verdict at the pre-registered threshold equals the generated verdict and gains.
const verdicts = parseVerdicts(resultsMd);
const v6 = verdicts.find((v) => v.id === 'H6');
const r6 = h6(results.hybrid, pre.hybridBar);
assert.equal(pre.hybridBar, 0.02);
assert.equal(r6.verdict, v6.verdict);
for (const r of r6.rows) assert.ok(v6.evidence.includes(`${r.backend} hybrid gain +${f3(r.gain)} nDCG`), `H6 gain ${r.backend}`);
assert.deepEqual(verdicts.map((v) => v.verdict), ['Refuted', 'Supported', 'Supported', 'Supported', 'Supported', 'Partially supported']);

// 4. Workload picker: the recorded tight cell with freshness required leaves pgvector and Qdrant.
const ok = (cell, opts) => pick(results, cell, { recallBar: pre.recallBar, hybridBar: pre.hybridBar, ...opts }).filter((r) => r.ok).map((r) => r.backend);
assert.deepEqual(ok('tenant_t5', { freshness: true, needHybrid: false }), ['pgvector', 'qdrant']);
assert.deepEqual(ok('none', { freshness: false, needHybrid: false }), ['faiss', 'pgvector', 'qdrant']);
assert.deepEqual(ok('none', { freshness: false, needHybrid: true }), ['faiss', 'qdrant']);

// 5. The limitations list parses from REPORT.md and carries no points (grades are internal).
const limits = parseLimits(read('REPORT.md'));
assert.ok(limits.length >= 10);
assert.ok(limits.every((t) => !/Minus \d/.test(t)));

console.log('stats ok', { c2: c2md, h6: r6.verdict, limitations: limits.length });
