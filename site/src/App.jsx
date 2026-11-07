import { useMemo, useState, useEffect, useId } from 'react';
import results from '../../results/cells.json';
import env from '../../results/env.json';
import qenv from '../../results_qdrant/env.json';
import resultsMd from '../../RESULTS.md?raw';
import hypMd from '../../HYPOTHESES.md?raw';
import auditMd from '../../AUDIT.md?raw';
import { shortfallCI, staleCI, staleSlots, c2, c2Agrees, h6, pick, parseVerdicts, parsePrereg, parseAudit } from './stats.js';

const REPO = 'https://github.com/JesunAhmadUshno/vector-systems-benchmark';
const blob = (p) => `${REPO}/blob/main/${p}`;
const f3 = (x) => x.toFixed(3);
const f2 = (x) => x.toFixed(2);
const pct = (x, d = 1) => `${(x * 100).toFixed(d)}%`;
const fmt = (n) => Math.round(n).toLocaleString('en-US');
const ms = (x) => (x < 10 ? `${f2(x)} ms` : x < 1000 ? `${x.toFixed(1)} ms` : `${(x / 1000).toFixed(2)} s`);

const PRE = parsePrereg(hypMd);
const VERDICTS = parseVerdicts(resultsMd);
const AUDIT = parseAudit(auditMd);
const TITLES = Object.fromEntries([...hypMd.matchAll(/^## (H\d): (.+)$/gm)].map((m) => [m[1], m[2]]));
const K = env.k;
const SEL = env.filter_selectivity_measured;

const CELLS = [
  ['none', 'Unfiltered'], ['tenant_t0', 'Tenant t0'], ['tenant_t2', 'Tenant t2'],
  ['tenant_t5', 'Tenant t5 (tight)'], ['article_group', 'Article group (correlated)'],
];
const CELL_LABEL = Object.fromEntries(CELLS);
const BACKENDS = ['faiss', 'pgvector', 'qdrant'];
const NAME = { faiss: 'FAISS', pgvector: 'pgvector', qdrant: 'Qdrant' };
const COLOR = { faiss: 'var(--c-faiss)', pgvector: 'var(--c-pg)', qdrant: 'var(--c-qd)' };
const QDRANT_NOTE = 'embedded local mode, exact brute force, not the server';
const find = (list, b, cell, arm) => list.find((e) => e.backend === b && e.cell === cell && (!arm || e.arm === arm));
const cell = (b, c) => find(results.cells, b, c);
const verdictClass = (v) => (v === 'Supported' ? 'good' : v === 'Refuted' ? 'bad' : 'warn');

const SECTIONS = [['top', 'Overview', '◎'], ['regime', 'Regime map', '▦'], ['trap', 'Trap', '⊘'], ['churn', 'Churn', '↻'], ['hybrid', 'Hybrid', '⇄'], ['picker', 'Picker', '◇'], ['hypotheses', 'Hypotheses', '✓'], ['limits', 'Limits', '⚑'], ['reproduce', 'Reproduce', '❯_']];

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) { els.forEach((e) => e.classList.add('in')); return; }
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: 0.08 });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);
}

function MenuBar() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 30000); return () => clearInterval(t); }, []);
  return (
    <div className="menubar" role="banner">
      <span className="apple" aria-hidden="true">◆</span>
      <a className="app" href="#top">Vector Systems Benchmark</a>
      <a className="m" href={blob('SPEC.md')}>Spec</a>
      <a className="m" href={blob('HYPOTHESES.md')}>Hypotheses</a>
      <a className="m" href={blob('RESULTS.md')}>Results</a>
      <span className="spacer" />
      <span className="status"><i /> Pre-registered</span>
      <a href={REPO}>GitHub ↗</a>
      <span className="clock">{now.toLocaleString('en-US', { weekday: 'short', hour: 'numeric', minute: '2-digit' })}</span>
    </div>
  );
}

function Dock() {
  const [active, setActive] = useState('top');
  useEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)), { rootMargin: '-45% 0px -50% 0px' });
    SECTIONS.forEach(([id]) => { const el = document.getElementById(id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, []);
  return (
    <nav className="dock" aria-label="Sections">
      {SECTIONS.map(([id, label, icon]) => (
        <a key={id} href={`#${id}`} className={active === id ? 'on' : ''} aria-current={active === id ? 'true' : undefined}>
          <span className="ico" aria-hidden="true">{icon}</span><span className="lbl">{label}</span>
        </a>
      ))}
    </nav>
  );
}

function Range({ label, value, min, max, step, onChange, show }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label} <span>{show}</span></label>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} />
    </div>
  );
}

export default function App() {
  useReveal();
  return (
    <div className="wrap">
      <MenuBar />
      <div className="glow" aria-hidden="true" />
      <Hero />
      <Regime />
      <Trap />
      <Churn />
      <Hybrid />
      <Picker />
      <Hypotheses />
      <Limits />
      <Reproduce />
      <Dock />
      <footer>
        Corpus: SQuAD v1.1 (Rajpurkar et al., 2016), {env.corpus_licence}. Embeddings: {env.embedding_model} ({env.embedding_model_licence}). Code: Apache-2.0.
        Every number on this page is read from <code>results/</code> and the repo’s generated Markdown at build time; the calculators run in your browser on those recorded numbers.
      </footer>
    </div>
  );
}

function Hero() {
  const ft = cell('faiss', 'tenant_t5'), fu = cell('faiss', 'none');
  const trap = find(results.trap, 'pgvector', 'trap_tenant_t2');
  const raw = find(results.churn, 'faiss', 'post_churn_none', 'raw');
  const holders = BACKENDS.filter((b) => b !== 'faiss' && cell(b, 'tenant_t5').recall10 === 1);
  const counts = VERDICTS.reduce((m, v) => ({ ...m, [v.verdict]: (m[v.verdict] || 0) + 1 }), {});
  return (
    <header className="card hero window" id="top" data-title="regime-map.md">
      <div className="head">
        <p className="eyebrow">Pre-registered benchmark · {BACKENDS.length} engines · one node</p>
        <span className="pill info">● {counts.Supported} supported · {counts['Partially supported']} partial · {counts.Refuted} refuted</span>
      </div>
      <h1>No vector engine wins everywhere. At {pct(SEL.tenant_t5, 0)} filter selectivity, FAISS recall falls to <em>{f3(ft.recall10)}</em>.</h1>
      <p className="sub">
        In the same cell {holders.map((b) => NAME[b]).join(' and ')} hold recall {f3(cell('pgvector', 'tenant_t5').recall10)}, and pgvector’s silent-shortfall trap shows up one band higher, at {pct(trap.selectivity, 0)} selectivity.
        FAISS, PostgreSQL with pgvector, and Qdrant were measured on one shared corpus as filter selectivity, update churn and hybrid demand change.
        Hypotheses and thresholds were committed before any experiment code. Everything below is the recorded run, with live calculators that rework its logic.
      </p>
      <div className="actions">
        <a className="btn primary" href="#trap">Open the trap calculator</a>
        <a className="btn ghost" href={blob('SPEC.md')}>Read the pre-registration</a>
        <span className="hint">Recorded run: {env.date_utc.slice(0, 10)}</span>
      </div>
      <div className="tiles">
        <div className="tile"><div className="num">{f2(fu.p95_ms)} ms</div><div className="cap">FAISS unfiltered p95 latency, at recall {f3(fu.recall10)} (in process)</div></div>
        <div className="tile"><div className="num">{f3(ft.recall10)}</div><div className="cap">FAISS recall@10 in the tight cell; {pct(ft.shortfall_rate)} of queries come back short</div></div>
        <div className="tile"><div className="num">{f3(trap.shortfall_rate)}</div><div className="cap">pgvector shortfall rate at defaults, selectivity {f3(trap.selectivity)}: {f2(trap.mean_returned)} of {K} results per query</div></div>
        <div className="tile"><div className="num">{f3(raw.stale_rate)}</div><div className="cap">FAISS stale rate after churn without bookkeeping: deleted ids still served</div></div>
      </div>
      <div className="strip" aria-label="Corpus and protocol">
        <span><b>{fmt(env.n_chunks)}</b> chunks</span>
        <span><b>{env.dim}</b>-dim {env.embedding_model}</span>
        <span>{env.corpus} · {env.corpus_licence}</span>
        <span>k = <b>{K}</b></span>
        <span>{env.n_queries} queries × {env.reps} reps (FAISS, pgvector) · {qenv.n_queries} × {qenv.reps} (Qdrant)</span>
      </div>
    </header>
  );
}

const METRICS = {
  recall10: { label: 'recall@10', fmt: f3, max: 1 },
  shortfall_rate: { label: 'Shortfall rate', fmt: f3, max: 1, ci: shortfallCI },
  mean_returned: { label: 'Mean returned', fmt: f2, max: K },
  p50_ms: { label: 'p50 latency', fmt: ms, log: true },
  p95_ms: { label: 'p95 latency', fmt: ms, log: true },
};

function Legend({ on = BACKENDS }) {
  return (
    <div className="legend">
      {on.map((b) => <span key={b}><i style={{ background: COLOR[b] }} />{NAME[b]}{b === 'qdrant' ? ` (${QDRANT_NOTE})` : ''}</span>)}
    </div>
  );
}

function Regime() {
  const [metric, setMetric] = useState('recall10');
  const [on, setOn] = useState({ faiss: true, pgvector: true, qdrant: true });
  const [hover, setHover] = useState(null);
  const m = METRICS[metric];
  const shown = BACKENDS.filter((b) => on[b]);
  const W = 960, H = 330, pad = { l: 56, r: 16, t: 16, b: 46 };
  const band = (W - pad.l - pad.r) / CELLS.length;
  const LO = 0.1, HI = 10000;
  const y = m.log
    ? (v) => pad.t + (1 - (Math.log10(Math.max(LO, v)) - Math.log10(LO)) / (Math.log10(HI) - Math.log10(LO))) * (H - pad.t - pad.b)
    : (v) => pad.t + (1 - v / m.max) * (H - pad.t - pad.b);
  const ticks = m.log ? [0.1, 1, 10, 100, 1000, 10000] : [0, 0.25, 0.5, 0.75, 1].map((t) => t * m.max);
  const x = (ci, bi) => pad.l + ci * band + band / 2 + (bi - 1) * Math.min(26, band / 5);
  const tipText = (e) => {
    const ci = m.ci && m.ci(e);
    return `${NAME[e.backend]} (${e.arm}) · ${CELL_LABEL[e.cell]}, selectivity ${f3(e.selectivity)}: ${m.label} ${m.fmt(e[metric])}${ci ? `, 95% Wilson CI ${f3(ci[0])} to ${f3(ci[1])}` : ''} · n = ${e.n_queries} queries × ${e.reps} reps${e.backend === 'qdrant' ? ` · ${QDRANT_NOTE}` : ''}`;
  };
  return (
    <section id="regime" className="card window reveal" data-title="cells.json — regime map">
      <div className="head">
        <div>
          <p className="eyebrow">Recorded replay · {results.cells.length} main cells</p>
          <h2>Five filter cells, three engines: the map has sharp edges.</h2>
          <p className="sub">
            Each point is one recorded cell from <a href={blob('results/cells.json')}>results/cells.json</a>. Pick a metric and toggle engines.
            Shortfall points carry Wilson 95% whiskers sized by each row’s own query count. Recall has no interval because per-query recall was not saved.
            {m.log && ' Latency is on a log scale and compares deployed shapes: FAISS in process, pgvector over a socket, Qdrant as embedded Python.'}
          </p>
        </div>
      </div>
      <div className="toolbar">
        <div className="seg" role="group" aria-label="Metric">
          {Object.entries(METRICS).map(([k, v]) => <button key={k} aria-pressed={metric === k} onClick={() => setMetric(k)}>{v.label}</button>)}
        </div>
        <div className="seg" role="group" aria-label="Engines shown">
          {BACKENDS.map((b) => <button key={b} aria-pressed={on[b]} onClick={() => setOn({ ...on, [b]: !on[b] })}><i className="dot" style={{ background: COLOR[b] }} />{NAME[b]}</button>)}
        </div>
      </div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Regime map: ${m.label} by filter cell and engine`} onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}><line className="axis" x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} /><text x={pad.l - 8} y={y(t) + 4} textAnchor="end">{m.log ? (t >= 1000 ? `${t / 1000} s` : `${t} ms`) : m.fmt(t)}</text></g>
        ))}
        {CELLS.map(([c, label], ci) => (
          <g key={c}>
            {ci > 0 && <line className="axis" x1={pad.l + ci * band} x2={pad.l + ci * band} y1={pad.t} y2={H - pad.b} strokeDasharray="3 4" />}
            <text x={pad.l + ci * band + band / 2} y={H - pad.b + 18} textAnchor="middle" style={{ fill: 'var(--text)' }}>{label}</text>
            <text x={pad.l + ci * band + band / 2} y={H - pad.b + 34} textAnchor="middle">selectivity {pct(SEL[c])}</text>
          </g>
        ))}
        {CELLS.map(([c], ci) => BACKENDS.map((b, bi) => {
          const e = cell(b, c);
          if (!on[b] || !e) return null;
          const ci95 = m.ci && m.ci(e);
          const active = hover === e;
          return (
            <g key={b + c} tabIndex={0} onMouseEnter={() => setHover(e)} onFocus={() => setHover(e)} style={{ cursor: 'pointer' }}>
              {ci95 && <line x1={x(ci, bi)} x2={x(ci, bi)} y1={y(ci95[0])} y2={y(ci95[1])} stroke={COLOR[b]} strokeWidth="2" />}
              {ci95 && [0, 1].map((j) => <line key={j} x1={x(ci, bi) - 5} x2={x(ci, bi) + 5} y1={y(ci95[j])} y2={y(ci95[j])} stroke={COLOR[b]} strokeWidth="2" />)}
              <circle cx={x(ci, bi)} cy={y(e[metric])} r={active ? 8 : 6} fill={COLOR[b]} stroke="var(--surface-strong)" strokeWidth="2" />
            </g>
          );
        }))}
      </svg>
      <Legend on={shown} />
      <div className="tip" aria-live="polite">{hover ? tipText(hover) : 'Hover or tab to a point for its value, sample size and arm.'}</div>
      <div style={{ overflowX: 'auto', marginTop: 12 }}>
        <table>
          <thead><tr><th>{m.label}</th>{CELLS.map(([c, l]) => <th key={c}>{l}</th>)}</tr></thead>
          <tbody>
            {shown.map((b) => (
              <tr key={b}>
                <td><b style={{ color: COLOR[b] }}>{NAME[b]}</b> <span className="hint">n {cell(b, 'none').n_queries} × {cell(b, 'none').reps}</span></td>
                {CELLS.map(([c]) => { const e = cell(b, c); return <td key={c}>{m.fmt(e[metric])}{m.ci && <div className="hint">{f3(m.ci(e)[0])} to {f3(m.ci(e)[1])}</div>}</td>; })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Trap() {
  const [ef, setEf] = useState(PRE.efDefault);
  const trapT2 = find(results.trap, 'pgvector', 'trap_tenant_t2');
  const trapT5 = find(results.trap, 'pgvector', 'trap_tenant_t5');
  const [logSel, setLogSel] = useState(Math.log10(trapT2.selectivity));
  const sel = 10 ** logSel;
  const r = c2(ef, sel, K);
  const W = 960, H = 300, pad = { l: 44, r: 24, t: 20, b: 40 };
  const sx = (s) => pad.l + ((Math.log10(s) + 3) / 3) * (W - pad.l - pad.r);
  const sy = (v) => pad.t + (1 - v / K) * (H - pad.t - pad.b);
  const curve = (e) => Array.from({ length: 121 }, (_, i) => { const s = 10 ** (-3 + i * 0.025); return `${sx(s)},${sy(c2(e, s, K).expected)}`; }).join(' ');
  const rows = [trapT2, trapT5].flatMap((t) => {
    const it = cell('pgvector', t.cell.replace('trap_', ''));
    const pred = c2(PRE.efDefault, t.selectivity, K).predicted;
    return [{ e: t, label: 'Defaults (iterative scan off)', pred, agrees: c2Agrees(t.mean_returned, pred, K) }, { e: it, label: 'Iterative scan on' }];
  });
  const recorded = [
    { e: trapT2, text: `recorded ${f2(trapT2.mean_returned)} (C2 predicts ${f2(c2(PRE.efDefault, trapT2.selectivity, K).predicted)})`, anchor: 'end', dx: -14 },
    { e: trapT5, text: `recorded ${f2(trapT5.mean_returned)}: planner leaves the index`, anchor: 'start', dx: 10 },
  ];
  return (
    <section id="trap" className="card window reveal" data-title="trap_defaults.sql — C2 calculator">
      <div className="head">
        <div>
          <p className="eyebrow">Live calculator · C2 candidate-starvation model</p>
          <h2>pgvector’s overfiltering trap lives at <em>{pct(trapT2.selectivity, 0)}</em> selectivity, not {pct(trapT5.selectivity, 0)}.</h2>
          <p className="sub">
            With iterative scan off, pgvector’s HNSW scan looks at hnsw.ef_search candidates and then applies the filter, so it can return only about ef_search × selectivity matches, capped at k = {K}.
            The calculator runs that model live (ported from <a href={blob('src/vectorbench/generate_results.py')}>generate_results.py</a>). The two black points are the recorded default-config cells.
          </p>
        </div>
        <span className={`pill ${r.short ? 'bad' : 'good'}`}>{r.short ? `● short by ${f2(r.missing)} per query` : '● full k returned'}</span>
      </div>
      <div className="grid2">
        <div className="controls" style={{ gridTemplateColumns: '1fr', margin: 0 }}>
          <Range label="hnsw.ef_search" value={ef} min={10} max={400} step={5} onChange={setEf} show={ef === PRE.efDefault ? `${ef} (default)` : ef} />
          <Range label="Filter selectivity (log scale)" value={logSel} min={-3} max={0} step={0.01} onChange={setLogSel} show={pct(sel, sel < 0.01 ? 2 : 1)} />
        </div>
        <div className="tiles" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 0 }}>
          <div className="tile"><div className="num">{f2(r.expected)}</div><div className="cap">expected matches of {K} (ef_search {ef} × {pct(sel, 2)})</div></div>
          <div className="tile"><div className="num">{pct(Math.min(1, K / ef), 1)}</div><div className="cap">selectivity below which this ef_search starts to fall short</div></div>
        </div>
      </div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Expected matches versus filter selectivity, with recorded pgvector trap cells" style={{ marginTop: 12 }}>
        {[0, K / 2, K].map((t) => <g key={t}><line className="axis" x1={pad.l} x2={W - pad.r} y1={sy(t)} y2={sy(t)} /><text x={pad.l - 8} y={sy(t) + 4} textAnchor="end">{t}</text></g>)}
        {[0.001, 0.01, 0.1, 1].map((s) => <g key={s}><line className="axis" x1={sx(s)} x2={sx(s)} y1={pad.t} y2={H - pad.b} /><text x={sx(s)} y={H - pad.b + 18} textAnchor={s === 1 ? 'end' : s === 0.001 ? 'start' : 'middle'}>{pct(s, s < 0.01 ? 1 : 0)}</text></g>)}
        <text x={(W + pad.l) / 2} y={H - 4} textAnchor="middle">filter selectivity (share of corpus admitted)</text>
        {ef !== PRE.efDefault && <polyline fill="none" stroke="var(--muted)" strokeDasharray="5 5" strokeWidth="1.5" points={curve(PRE.efDefault)} />}
        <polyline fill="none" stroke="var(--c-pg)" strokeWidth="2.5" points={curve(ef)} />
        {[trapT2, trapT5].map((t) => <circle key={t.cell} cx={sx(t.selectivity)} cy={sy(cell('pgvector', t.cell.replace('trap_', '')).mean_returned)} r="9" fill="none" stroke="var(--good)" strokeWidth="2" />)}
        {recorded.map(({ e, text, anchor, dx }) => (
          <g key={e.cell}>
            <line x1={sx(e.selectivity)} x2={sx(e.selectivity)} y1={sy(c2(PRE.efDefault, e.selectivity, K).expected)} y2={sy(e.mean_returned)} stroke="var(--text)" strokeDasharray="2 3" opacity="0.5" />
            <circle cx={sx(e.selectivity)} cy={sy(e.mean_returned)} r="5.5" fill="var(--text)" />
            <text x={sx(e.selectivity) + dx} y={sy(e.mean_returned) + (e === trapT5 ? 22 : 4)} textAnchor={anchor} style={{ fill: 'var(--text)' }}>{text}</text>
          </g>
        ))}
        <circle cx={sx(sel)} cy={sy(r.expected)} r="6" fill="var(--c-pg)" stroke="var(--surface-strong)" strokeWidth="2" />
      </svg>
      <div className="legend">
        <span><i style={{ background: 'var(--c-pg)' }} />C2 model at ef_search {ef}{ef !== PRE.efDefault ? ` (dashed: default ${PRE.efDefault})` : ''}</span>
        <span><i style={{ background: 'var(--text)' }} />Recorded, defaults arm</span>
        <span><i style={{ background: 'transparent', border: '2px solid var(--good)' }} />Recorded, iterative scan on</span>
      </div>
      <div style={{ overflowX: 'auto', marginTop: 16 }}>
        <table>
          <thead><tr><th>Cell</th><th>pgvector arm</th><th>recall@10</th><th>Shortfall (95% CI)</th><th>Mean returned</th><th>C2 at ef {PRE.efDefault}</th></tr></thead>
          <tbody>
            {rows.map(({ e, label, pred, agrees }) => {
              const ci = shortfallCI(e);
              return (
                <tr key={e.cell + e.arm}>
                  <td>selectivity {f3(e.selectivity)}</td><td>{label}</td><td>{f3(e.recall10)}</td>
                  <td className={e.shortfall_rate > 0 ? 'no' : 'ok'}>{f3(e.shortfall_rate)} <span className="hint">({f3(ci[0])} to {f3(ci[1])})</span></td>
                  <td>{f2(e.mean_returned)}</td>
                  <td>{pred == null ? '—' : <>{f2(pred)} <span className={`pill ${agrees ? 'good' : 'warn'}`}>{agrees ? 'agrees' : 'disagrees'}</span></>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="hint" style={{ marginTop: 10 }}>
        At {pct(trapT5.selectivity)} the model predicts {f2(c2(PRE.efDefault, trapT5.selectivity, K).predicted)} but {f2(trapT5.mean_returned)} came back. The study attributes this to the planner leaving the ANN index at very low selectivity (research pack row 10). No EXPLAIN plan was captured, so that mechanism is unverified here.
      </p>
    </section>
  );
}

const ARM_LABEL = { raw: 'no bookkeeping', bookkeeping: '+ bookkeeping', iterative: 'iterative', native: 'native delete' };

function Churn() {
  const rows = BACKENDS.flatMap((b) => results.churn.filter((e) => e.backend === b));
  const W = 560, rowH = 46, pad = { l: 230, r: 16, t: 26, b: 30 }, H = pad.t + rows.length * rowH + pad.b;
  const lo = 0.3;
  const x = (v) => pad.l + ((v - lo) / (1 - lo)) * (W - pad.l - pad.r);
  const maxStale = Math.max(...rows.map((e) => staleCI(e)[1]));
  const scale = Math.ceil(maxStale * 20) / 20;
  return (
    <section id="churn" className="card window reveal" data-title="post_churn.log">
      <p className="eyebrow">Recorded · delete and insert cycle</p>
      <h2>Without bookkeeping, FAISS keeps serving <em>deleted</em> vectors.</h2>
      <p className="sub">
        Recall before and after one churn cycle, and the share of returned slots that hold a deleted id. Dashed ticks mark the pre-registered H5 bound: a recall drop of less than {PRE.dropBar}.
        Stale whiskers are Wilson 95% intervals over returned slots; slots within a query are not independent, so they are narrower than a query-level interval would be.
      </p>
      <div className="grid2" style={{ marginTop: 16 }}>
        <div>
          <h3>recall@10, pre-churn (hollow) to post-churn (filled)</h3>
          <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Pre-churn versus post-churn recall by engine and arm">
            {[0.4, 0.6, 0.8, 1].map((t) => <g key={t}><line className="axis" x1={x(t)} x2={x(t)} y1={pad.t - 8} y2={H - pad.b} /><text x={x(t)} y={H - 10} textAnchor={t === 1 ? 'end' : 'middle'}>{t.toFixed(1)}</text></g>)}
            {rows.map((e, i) => {
              const yy = pad.t + i * rowH + rowH / 2;
              return (
                <g key={e.backend + e.arm + e.cell}>
                  <text x={0} y={yy - 2} style={{ fill: 'var(--text)', fontSize: 13 }}>{NAME[e.backend]} {ARM_LABEL[e.arm]}</text>
                  <text x={0} y={yy + 13}>{e.cell.endsWith('none') ? 'unfiltered' : 'tight filter'} · {f3(e.pre_churn_recall10)} → {f3(e.recall10)}</text>
                  <line x1={x(e.pre_churn_recall10 - PRE.dropBar)} x2={x(e.pre_churn_recall10 - PRE.dropBar)} y1={yy - 9} y2={yy + 9} stroke="var(--warn)" strokeDasharray="3 2" strokeWidth="1.5" />
                  <line x1={x(e.pre_churn_recall10)} x2={x(e.recall10)} y1={yy} y2={yy} stroke={COLOR[e.backend]} strokeWidth="3" opacity="0.5" />
                  <circle cx={x(e.pre_churn_recall10)} cy={yy} r="5" fill="var(--surface-strong)" stroke={COLOR[e.backend]} strokeWidth="2" />
                  <circle cx={x(e.recall10)} cy={yy} r="5" fill={COLOR[e.backend]} />
                </g>
              );
            })}
          </svg>
        </div>
        <div>
          <h3>Stale rate after churn (H5 expects 0, except FAISS with no bookkeeping)</h3>
          <div className="bars" style={{ marginTop: 14 }}>
            {rows.map((e) => {
              const ci = staleCI(e);
              return (
                <div className="bar-row" key={e.backend + e.arm + e.cell}>
                  <div className="lab"><span>{NAME[e.backend]} {ARM_LABEL[e.arm]} · {e.cell.endsWith('none') ? 'unfiltered' : 'tight'}</span><b>{f3(e.stale_rate)}</b></div>
                  <div className="track">
                    <div className="fill" style={{ width: `${(e.stale_rate / scale) * 100}%`, background: e.stale_rate > 0 ? 'var(--bad)' : 'var(--good)' }} />
                    <div className="whisk" style={{ left: `${(ci[0] / scale) * 100}%`, width: `${Math.max(0.6, ((ci[1] - ci[0]) / scale) * 100)}%` }} />
                  </div>
                  <div className="hint">95% CI {f3(ci[0])} to {f3(ci[1])} over {fmt(staleSlots(e))} slots · {e.n_queries} queries × {e.reps} reps</div>
                </div>
              );
            })}
          </div>
          <p className="hint" style={{ marginTop: 10 }}>Bar scale 0 to {scale}.</p>
        </div>
      </div>
    </section>
  );
}

function Hybrid() {
  const [metric, setMetric] = useState('ndcg10');
  const [thr, setThr] = useState(PRE.hybridBar);
  const res = h6(results.hybrid, thr);
  const arms = [['dense', 'Dense'], ['bm25_shared', 'Shared BM25'], ['hybrid', 'Hybrid (RRF)']];
  const W = 960, H = 260, pad = { l: 44, r: 12, t: 24, b: 40 };
  const max = 0.7;
  const y = (v) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const gw = (W - pad.l - pad.r) / BACKENDS.length, bw = Math.min(70, gw / 5);
  const shade = { dense: 0.45, bm25_shared: 0.22, hybrid: 1 };
  return (
    <section id="hybrid" className="card window reveal" data-title="rrf_fusion.py — hybrid search">
      <div className="head">
        <div>
          <p className="eyebrow">Recorded · sensitivity view</p>
          <h2>Hybrid fusion pays where the lexical arm is the <em>shared</em> BM25.</h2>
          <p className="sub">
            Dense, shared BM25 and hybrid (RRF) quality per engine on {results.hybrid.faiss.n_questions_scored} SQuAD questions. The pgvector hybrid arm fuses PostgreSQL full-text ranking (ts_rank), not the shared BM25, so its result is not encoder-controlled.
            The threshold slider re-applies the H6 rule to the recorded means; it is a sensitivity view, not a new test, and no per-question data exists for a significance test.
          </p>
        </div>
        <div className="seg" role="group" aria-label="Hybrid metric">
          {[['ndcg10', 'nDCG@10'], ['recall100', 'recall@100']].map(([k, l]) => <button key={k} aria-pressed={metric === k} onClick={() => setMetric(k)}>{l}</button>)}
        </div>
      </div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Hybrid search ${metric === 'ndcg10' ? 'nDCG@10' : 'recall@100'} by engine and arm`}>
        {[0, 0.2, 0.4, 0.6].map((t) => <g key={t}><line className="axis" x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} /><text x={pad.l - 8} y={y(t) + 4} textAnchor="end">{t.toFixed(1)}</text></g>)}
        {BACKENDS.map((b, gi) => {
          const h = results.hybrid[b];
          return (
            <g key={b}>
              {arms.map(([a], ai) => {
                const v = h.arms[a][metric], bx = pad.l + gi * gw + gw / 2 + (ai - 1.5) * (bw + 6);
                return (
                  <g key={a}>
                    <rect x={bx} width={bw} y={y(v)} height={y(0) - y(v)} rx="5" fill={COLOR[b]} opacity={shade[a]} />
                    <text x={bx + bw / 2} y={y(v) - 6} textAnchor="middle" style={{ fill: 'var(--text)' }}>{f3(v)}</text>
                  </g>
                );
              })}
              <text x={pad.l + gi * gw + gw / 2} y={H - 14} textAnchor="middle" style={{ fill: 'var(--text)' }}>{NAME[b]}{b === 'pgvector' ? ' (lexical arm: ts_rank)' : ''}</text>
            </g>
          );
        })}
      </svg>
      <div className="legend">{arms.map(([a, l]) => <span key={a}><i style={{ background: 'var(--muted)', opacity: shade[a] }} />{l}</span>)}</div>
      <div className="grid2" style={{ marginTop: 18, alignItems: 'start' }}>
        <div>
          <Range label="H6 hybrid-gain threshold (nDCG@10)" value={thr} min={0} max={0.1} step={0.005} onChange={setThr} show={thr === PRE.hybridBar ? `${thr.toFixed(3)} (pre-registered)` : thr.toFixed(3)} />
          <p className="hint">Verdict at this threshold: <span className={`pill ${verdictClass(res.verdict)}`}>{res.verdict}</span>{thr !== PRE.hybridBar && ' (the published verdict uses the pre-registered value)'}</p>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead><tr><th>Engine</th><th>Fusion</th><th>Gain (nDCG@10)</th><th>H6</th></tr></thead>
            <tbody>
              {res.rows.map((r) => (
                <tr key={r.backend}><td>{NAME[r.backend]}</td><td className="hint">{results.hybrid[r.backend].fusion}</td><td>{r.gain >= 0 ? '+' : ''}{f3(r.gain)}</td><td className={r.pass ? 'ok' : 'no'}>{r.pass ? 'pass' : 'fail'}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Picker() {
  const [c, setC] = useState('tenant_t5');
  const [fresh, setFresh] = useState(true);
  const [hyb, setHyb] = useState(false);
  const rows = useMemo(() => pick(results, c, { freshness: fresh, needHybrid: hyb, recallBar: PRE.recallBar, hybridBar: PRE.hybridBar }), [c, fresh, hyb]);
  const id = useId();
  return (
    <section id="picker" className="card window reveal" data-title="workload_picker.app">
      <p className="eyebrow">Recorded lookup</p>
      <h2>Describe your workload. See which measured engine met the bar.</h2>
      <p className="sub">
        A lookup over the recorded cells, not a prediction. An engine passes when its arm reached recall@10 ≥ {PRE.recallBar} (the H4 operating point) with zero shortfall in that cell,
        plus zero stale results after churn and a hybrid gain ≥ {PRE.hybridBar} if you ask for them. Churn was recorded only in the unfiltered and tight cells, so the nearest one is used.
      </p>
      <div className="controls" style={{ marginTop: 16 }}>
        <div className="field"><label htmlFor={`${id}-cell`}>Filter selectivity</label>
          <select id={`${id}-cell`} value={c} onChange={(e) => setC(e.target.value)}>
            {CELLS.map(([k, l]) => <option key={k} value={k}>{l}: {pct(SEL[k])}</option>)}
          </select>
        </div>
        <label className="check" htmlFor={`${id}-fresh`}><input id={`${id}-fresh`} type="checkbox" checked={fresh} onChange={(e) => setFresh(e.target.checked)} /> Freshness after deletes matters</label>
        <label className="check" htmlFor={`${id}-hyb`}><input id={`${id}-hyb`} type="checkbox" checked={hyb} onChange={(e) => setHyb(e.target.checked)} /> Hybrid (lexical + dense) matters</label>
      </div>
      <div className="pick">
        {rows.map((r) => (
          <div className={`tile ${r.ok ? 'pass' : ''}`} key={r.backend}>
            <div className="head" style={{ marginBottom: 8 }}>
              <h3 style={{ color: COLOR[r.backend] }}>{NAME[r.backend]} <span className="hint">({r.arm})</span></h3>
              <span className={`pill ${r.ok ? 'good' : 'bad'}`}>{r.ok ? 'Met the bar' : 'Did not'}</span>
            </div>
            <ul className="checks">
              {r.checks.map((k) => <li key={k.k} className={k.ok ? 'ok' : 'no'}><span aria-hidden="true">{k.ok ? '✓' : '✗'}</span> {k.k} <span className="hint">({k.v})</span></li>)}
            </ul>
            <p className="hint" style={{ margin: '8px 0 0' }}>p95 {ms(r.p95)} · n {r.n} × {r.reps}{r.backend === 'qdrant' ? ` · ${QDRANT_NOTE}` : r.backend === 'faiss' ? ' · in process' : ' · over a socket'}</p>
          </div>
        ))}
      </div>
      <p className="hint" style={{ marginTop: 12 }}>Latency is shown, not scored: it compares deployed shapes, not index algorithms.{fresh && ' FAISS freshness uses its bookkeeping arm; without bookkeeping it serves deleted ids.'}</p>
    </section>
  );
}

const NOTES = {
  H2: 'The pre-registered H2 also lists the post-churn cell; the computation uses the five main cells, now disclosed in the evidence (DECISIONS.md D11).',
  H3: 'Qdrant ran in embedded local mode, which is exact by construction, so this says nothing about the server’s filtered HNSW. A relabel to Inconclusive is proposed in docs/research-review.md and not applied.',
};

function Hypotheses() {
  const refuted = VERDICTS.filter((v) => v.verdict === 'Refuted').length;
  return (
    <section id="hypotheses" className="card window reveal" data-title="HYPOTHESES.md — scorecard">
      <p className="eyebrow">Pre-registered hypotheses · verdicts generated</p>
      <h2>{VERDICTS.length} predictions, committed before the code. {refuted} {refuted === 1 ? 'was' : 'were'} <em>refuted</em>.</h2>
      <p className="sub">Verdict words and evidence are read from the generated <a href={blob('RESULTS.md')}>RESULTS.md</a> at build time; the build re-derives H6 in JavaScript and fails if they disagree.</p>
      <div className="grid2" style={{ marginTop: 16 }}>
        {VERDICTS.map((v) => (
          <div className="tile" key={v.id}>
            <div className="head" style={{ marginBottom: 6 }}><h3>{v.id}: {TITLES[v.id]}</h3><span className={`pill ${verdictClass(v.verdict)}`}>{v.verdict}</span></div>
            <details><summary className="hint">Evidence</summary><p className="hint" style={{ margin: '6px 0 0', fontSize: 13 }}>{v.evidence}</p></details>
            {NOTES[v.id] && <p className="hint" style={{ margin: '8px 0 0' }}><b>Caveat.</b> {NOTES[v.id]}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

function Limits() {
  const max = Math.max(...AUDIT.items.map((i) => i.minus));
  const threats = [
    ['Qdrant is embedded local mode', `Its recall is exact by construction and its latency (up to ${ms(Math.max(...results.cells.filter((e) => e.backend === 'qdrant').map((e) => e.p95_ms)))} p95) is a Python scan, not the server product.`],
    ['Client-shape latency asymmetry', 'FAISS runs in process, pgvector over a socket, Qdrant as embedded Python: latency ranks deployed shapes, not index algorithms.'],
    ['One corpus, one model, one scale', `${fmt(env.n_chunks)} chunks of ${env.corpus}, ${env.embedding_model}, one chunk size and one churn rate. Regime boundaries can move with any of them.`],
    ['Possible pgvector contention', 'The pgvector run shared the machine with a lost Qdrant attempt for part of its duration, which may inflate its latency tails. Disclosed, not corrected.'],
    ['Unequal samples', `Qdrant ran ${qenv.n_queries} queries × ${qenv.reps} reps against ${env.n_queries} × ${env.reps} for the others (DECISIONS.md D10).`],
    ['No per-query data', 'Recall, nDCG and latency vectors were not saved, so only shortfall and stale rates carry intervals here, and hybrid has no significance test.'],
  ];
  return (
    <section id="limits" className="card window reveal" data-title="AUDIT.md — limitations">
      <p className="eyebrow">Limitations and audit</p>
      <h2>Graded {fmt(AUDIT.grade)} of {fmt(AUDIT.scale)}, with every deduction itemized.</h2>
      <p className="sub">The study’s own audit, parsed from <a href={blob('AUDIT.md')}>AUDIT.md</a>. Deductions total {fmt(AUDIT.total)}; nothing is rounded up.</p>
      <div className="grid2" style={{ marginTop: 16, alignItems: 'start' }}>
        <div className="bars">
          {AUDIT.items.map((i) => (
            <div className="bar-row" key={i.text}>
              <div className="lab"><span>{i.text.split(/: |; |\. /)[0]}</span><b>−{fmt(i.minus)}</b></div>
              <div className="track"><div className="fill" style={{ width: `${(i.minus / max) * 100}%`, background: 'var(--warn)' }} /></div>
            </div>
          ))}
        </div>
        <div className="threats">
          {threats.map(([t, d]) => <div className="tile" key={t}><h3>{t}</h3><p className="hint" style={{ margin: '4px 0 0' }}>{d}</p></div>)}
        </div>
      </div>
    </section>
  );
}

function Reproduce() {
  const versions = [
    ['faiss', env.faiss], ['qdrant_client', env.qdrant_client], ['pgvector', env.pgvector], ['PostgreSQL', env.postgres.split(' (')[0].replace('PostgreSQL ', '')],
    ['numpy', env.numpy], ['model2vec', env.model2vec], ['python', env.python], ['cpu', env.cpu],
  ];
  const docs = [
    ['SPEC.md', 'Spec', 'Pre-registered study design'],
    ['HYPOTHESES.md', 'Hypotheses', 'H1 to H6, thresholds, falsifiers'],
    ['METHODS.md', 'Methods', 'Formulas, controls, threats'],
    ['RESULTS.md', 'Results', 'Generated, never hand-edited'],
    ['AUDIT.md', 'Audit', 'Run integrity, licences, grade'],
    ['docs/research-review.md', 'Research review', 'Rubric grade and open gaps'],
  ];
  return (
    <section id="reproduce" className="card window reveal" data-title="Terminal — reproduce">
      <p className="eyebrow">Reproduce it</p>
      <h2>One harness reruns the study; the results file regenerates the page.</h2>
      <ol className="steps" style={{ marginTop: 16 }}>
        <li><span className="n">1</span><div><b>Install and test</b><div className="hint"><code>python -m pip install -r requirements.txt && python -m pip install -e . && python -m pytest tests/</code></div></div></li>
        <li><span className="n">2</span><div><b>Run all three engines</b><div className="hint"><code>python -m vectorbench.run_benchmark --backends faiss,qdrant,pgvector</code> (needs local PostgreSQL with pgvector and a database named vsbench)</div></div></li>
        <li><span className="n">3</span><div><b>Regenerate the results</b><div className="hint"><code>python -m vectorbench.generate_results</code> rewrites RESULTS.md from results/*.json; this site rebuilds from the same files.</div></div></li>
      </ol>
      <div className="grid2" style={{ marginTop: 20, alignItems: 'start' }}>
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead><tr><th>Component</th><th>Version (results/env.json)</th></tr></thead>
            <tbody>{versions.map(([k, v]) => <tr key={k}><td className="mono">{k}</td><td>{v}</td></tr>)}</tbody>
          </table>
        </div>
        <div>
          <h3>Pre-registration order</h3>
          <p className="hint" style={{ marginTop: 6 }}>
            SPEC.md and HYPOTHESES.md were committed in <a href={`${REPO}/commit/838e6da`}><span className="mono">838e6da</span></a>, before the harness in <a href={`${REPO}/commit/4b559bd`}><span className="mono">4b559bd</span></a>. <a href={`${REPO}/commits/main`}>See the history</a>.
          </p>
          <div className="docs" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 12 }}>
            {docs.map(([p, t, d]) => <a key={p} href={blob(p)}><b>{t}</b><small>{d}</small></a>)}
          </div>
        </div>
      </div>
    </section>
  );
}
