// Pure computations used by the page. stats.check.mjs runs every one of them against
// the repo's own files (results/*.json, RESULTS.md, HYPOTHESES.md, REPORT.md) before each build.

// Wilson score 95% interval, same formula as wilson() in src/vectorbench/generate_results.py.
export function wilson(p, n, z = 1.959964) {
  if (n <= 0) return [0, 1];
  const den = 1 + (z * z) / n, c = (p + (z * z) / (2 * n)) / den;
  const h = (z / den) * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n));
  return [Math.max(0, c - h), Math.min(1, c + h)];
}

// Shortfall is a per-query yes/no outcome: n is the number of queries.
export const shortfallCI = (e) => wilson(e.shortfall_rate, e.n_queries);
// Stale rate is a share of returned slots: n is queries x mean returned.
export const staleSlots = (e) => Math.round(e.n_queries * e.mean_returned);
export const staleCI = (e) => wilson(e.stale_rate, staleSlots(e));

// C2 candidate-starvation model (HYPOTHESES.md C2, ported from c2_check in generate_results.py):
// with the HNSW index plan, a filter keeps about ef_search x selectivity of the candidates.
export function c2(efSearch, selectivity, k) {
  const predicted = efSearch * selectivity;
  const expected = Math.min(k, predicted);
  return { predicted, expected, missing: k - expected, short: expected < k };
}
export const c2Agrees = (measured, predicted, k) => {
  const capped = Math.min(k, predicted);
  return Math.abs(measured - capped) <= 0.1 * Math.max(capped, 1e-9);
};

// H6 rule from generate_results.py: gain = hybrid nDCG@10 - dense nDCG@10, passes at >= threshold.
export function h6(hybrid, threshold) {
  const rows = Object.entries(hybrid).map(([b, h]) => {
    const gain = h.arms.hybrid.ndcg10 - h.arms.dense.ndcg10;
    return { backend: b, gain, pass: gain >= threshold };
  });
  const passed = rows.filter((r) => r.pass).length;
  const verdict = passed === rows.length ? 'Supported' : passed > 0 ? 'Partially supported' : 'Refuted';
  return { rows, verdict };
}

// Workload picker: for one recorded cell, which backend meets the bar.
export function pick({ cells, churn, hybrid }, cell, { freshness, needHybrid, recallBar, hybridBar }) {
  const churnCell = cell === 'tenant_t5' || cell === 'article_group' ? 'post_churn_tenant_t5' : 'post_churn_none';
  const rows = [];
  for (const e of cells.filter((c) => c.cell === cell)) {
    const checks = [
      { k: `recall@10 ≥ ${recallBar}`, ok: e.recall10 >= recallBar, v: e.recall10.toFixed(3) },
      { k: 'zero shortfall', ok: e.shortfall_rate === 0, v: e.shortfall_rate.toFixed(3) },
    ];
    if (freshness) {
      const arm = e.backend === 'faiss' ? 'bookkeeping' : undefined;
      const c = churn.find((x) => x.backend === e.backend && x.cell === churnCell && (!arm || x.arm === arm));
      checks.push({ k: 'zero stale after churn', ok: !!c && c.stale_rate === 0, v: c ? c.stale_rate.toFixed(3) : 'n/a' });
    }
    if (needHybrid) {
      const h = hybrid[e.backend];
      const gain = h ? h.arms.hybrid.ndcg10 - h.arms.dense.ndcg10 : null;
      checks.push({ k: `hybrid gain ≥ ${hybridBar}`, ok: gain != null && gain >= hybridBar, v: gain == null ? 'n/a' : `${gain >= 0 ? '+' : ''}${gain.toFixed(3)}` });
    }
    rows.push({ backend: e.backend, arm: e.arm, p95: e.p95_ms, n: e.n_queries, reps: e.reps, checks, ok: checks.every((c) => c.ok), churnCell });
  }
  return rows;
}

// ---- Markdown parsers: verdicts, thresholds and the limitations come from the repo's own text ----
const need = (m, what) => { if (!m) throw new Error(`could not parse ${what}`); return m; };
const num = (s) => +String(s).replace(/,/g, '');

export function parseVerdicts(resultsMd) {
  const out = [...resultsMd.matchAll(/^\| (H\d) \| ([^|]+?) \| (.+) \|$/gm)].map((m) => ({ id: m[1], verdict: m[2], evidence: m[3] }));
  need(out.length === 6, 'six hypothesis rows in RESULTS.md');
  return out;
}

export function parseC2(resultsMd) {
  const m = [...resultsMd.matchAll(/the prediction is ([\d.]+) and the measured mean returned is\s+([\d.]+)/g)];
  need(m.length === 2, 'C2 sentence in RESULTS.md');
  return m.map((x) => ({ predicted: +x[1], measured: +x[2] }));
}

export function parsePrereg(hypMd) {
  return {
    efDefault: +need(hypMd.match(/default hnsw\.ef_search = (\d+)/), 'ef_search default')[1],
    recallBar: +need(hypMd.match(/unfiltered\s+recall@10 at or above ([\d.]+)/), 'H4 recall bar')[1],
    dropBar: +need(hypMd.match(/drops by less than ([\d.]+)/), 'H5 recall drop bound')[1],
    hybridBar: +need(hypMd.match(/at least ([\d.]+)\s+above\s+dense/), 'H6 threshold')[1],
  };
}

export function parseLimits(reportMd) {
  const section = need(reportMd.match(/Itemized limitations of this build[^\n]*\n\n([\s\S]*?)\n\n## /), 'limitations list in REPORT.md');
  const items = section[1].split(/^- /m).slice(1).map((s) => s.replace(/\s+/g, ' ').trim());
  need(items.length > 0, 'limitation items');
  return items;
}
