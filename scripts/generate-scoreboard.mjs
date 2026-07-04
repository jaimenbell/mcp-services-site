#!/usr/bin/env node
// generate-scoreboard.mjs — renders scoreboard.html from the fleet's own
// signal-validation source of truth. No build tooling, no deps (this repo
// has no package.json — see generate-og-image.mjs for the same constraint).
//
// WHAT THIS IS: the public, stripped render of the internal fleet's
// "Signal Validation Scoreboard" — the same VALIDATED / UNVALIDATED /
// ANTI-PREDICTIVE / THIN-EDGE status enum and the same Holm/BH-FDR
// promotion discipline the trading fleet holds itself to before any
// capital gets sized on a signal. This page holds a *data-feed product
// claim* to the identical bar: nothing gets marketed as accurate before
// this scoreboard says so, in public, with a citation.
//
// SOURCES (see the per-row HTML comment for the exact citation on every
// number rendered):
//   1. the vault/Reports/Signal Validation Scoreboard.md — the fleet's own
//      hand-maintained "single source of truth for signal validation
//      status" (its own frontmatter says so). Parsed below as markdown
//      tables. This is the canonical list of 47 backtest-unit rows.
//   2. OVERRIDES (below) — point-in-time corrections this generator run
//      independently verified against LIVE data that the vault doc (last
//      hand-edited 2026-05-21) does not yet reflect. Today's whale-tracker
//      confluence override was produced by re-running
//      research/whale_flow_check.py against the CURRENT
//      whale-tracker/data/signal_log.jsonl during this same generation
//      pass — see the override's `evidence` field for the exact numbers.
//
// REGENERATION: this script is run BY HAND, not on a schedule:
//   node scripts/generate-scoreboard.mjs
// A future auto-regen hook (schtask + the whale_flow_check.py re-run
// wired to write a persisted JSON snapshot instead of stdout-only prints)
// is NOTED, not built here — see FINDINGS at the bottom of this file.

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.join(__dirname, '..')
const OUT_HTML = path.join(REPO_ROOT, 'scoreboard.html')

// Absolute path to the vault note this machine already treats as the
// fleet's canonical scoreboard. Same "read straight off this machine's
// local project tree" pattern generate-og-image.mjs uses for Chrome.
const VAULT_SCOREBOARD_MD = path.join(
  'C:', 'Users', 'jaime', 'projects', 'the vault', 'Reports',
  'Signal Validation Scoreboard.md'
)

const GENERATED_AT = new Date().toISOString()

// ---------------------------------------------------------------------
// 1. Parse the vault markdown scoreboard into structured rows.
// ---------------------------------------------------------------------

function parseScoreboardMarkdown(md) {
  const lines = md.split(/\r?\n/)
  const rows = []
  let currentSection = null

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const h = line.match(/^#{2,3}\s+(.*)$/)
    if (h) {
      currentSection = h[1].trim()
      continue
    }
    // A data row: | `signal_source` | owning_bot | STATUS | wave | weight | notes |
    // Skip header/separator rows (the separator is all dashes/pipes/colons).
    if (line.startsWith('|') && line.includes('signal_source') === false) {
      const cells = line.split('|').slice(1, -1).map((c) => c.trim())
      if (cells.length < 6) continue
      if (/^:?-+:?$/.test(cells[0])) continue // separator row
      const [sigRaw, owning_bot, status, wave, weight, notes] = cells
      const signal_source = sigRaw.replace(/`/g, '').trim()
      if (!signal_source || signal_source.toLowerCase() === 'signal_source') continue
      rows.push({
        signal_source,
        owning_bot: owning_bot || '—',
        status: status.trim(),
        wave: wave.trim(),
        weight: weight.trim(),
        notes: notes.trim(),
        section: currentSection,
      })
    }
  }
  return rows
}

let vaultRows = []
let vaultReadError = null
try {
  const md = fs.readFileSync(VAULT_SCOREBOARD_MD, 'utf-8')
  vaultRows = parseScoreboardMarkdown(md)
} catch (e) {
  vaultReadError = e.message
}

// ---------------------------------------------------------------------
// 2. Known overrides — LIVE-verified corrections the vault doc's own
//    last_updated (2026-05-21) predates. Every override cites the exact
//    command + numbers that produced it. Do not add an override without
//    a reproducible command behind it.
// ---------------------------------------------------------------------

const OVERRIDES = {
  'whale-tracker.confluence': {
    status: 'UNVALIDATED-PENDING-REPRO',
    oos_progress: 'OOS BLOCKED — 44 calendar days of ticker-scoped signal history (2026-04-07→2026-05-21) vs 90-day minimum; embargo (14d) consumes the entire 30% OOS window',
    n: 127,
    live_stat: 'rho=+0.1360, t=+1.535, p=0.1247 @10d (full-sample, IS-biased — Spearman re-test, NOT the original win-rate methodology)',
    evidence: 'research/whale_flow_check.py, re-run 2026-07-04 against whale-tracker/data/signal_log.jsonl (1218 rows) during scoreboard generation. Reverses the vault scoreboard\'s VALIDATED classification (70.5% win-rate @10d, p=0.0004, 2026-05-20 methodology) — a Spearman re-test on the same signal returned NO-EDGE (p=0.1247), an unresolved methodology mismatch per the vault\'s own Learning/Glossary ("Scoreboard and VALIDATED promotion") and the 2026-07-03 Data Feed Products design doc. Publishing the more cautious label per the "never price ahead of the honesty label" rule.',
  },
}

// ---------------------------------------------------------------------
// 3. Normalize to the public display enum requested for this page:
//    VALIDATED / UNVALIDATED / INSUFFICIENT_DATA / REMOVED (anti-edge)
//    THIN-EDGE is kept as its own honest label (structural cap, not a
//    backtest verdict) rather than force-fit into the four above.
// ---------------------------------------------------------------------

function displayStatus(raw) {
  const s = raw.toUpperCase()
  if (s === 'VALIDATED') return { key: 'validated', label: 'VALIDATED' }
  if (s === 'ANTI-PREDICTIVE') return { key: 'removed', label: 'REMOVED (anti-edge)' }
  if (s === 'THIN-EDGE') return { key: 'thin', label: 'THIN-EDGE (capped)' }
  if (s === 'UNVALIDATED-PENDING-REPRO') return { key: 'pending', label: 'UNVALIDATED — PENDING REPRO' }
  return { key: 'unvalidated', label: 'UNVALIDATED' }
}

// Pull an "OOS / wave progress" hint out of free-text notes where one is
// legible; otherwise the honest answer is "—" (not yet backtested at all).
function oosProgressFromNotes(notes, wave) {
  const insufficient = notes.match(/INSUFFICIENT[- ]DATA[^;]*/i)
  if (insufficient) return insufficient[0]
  const clockGate = notes.match(/(\d+)-day (?:calendar )?clock[^;]*/i)
  if (clockGate) return clockGate[0]
  if (/^Wave \d/.test(wave)) return `Wave ${wave.match(/\d+/)?.[0] ?? wave} — queued, not yet run`
  if (wave === 'Parallel') return 'parallel-track — scope decision pending, not a backtest'
  return '—'
}

const rows = vaultRows.map((r) => {
  const override = OVERRIDES[r.signal_source]
  const statusRaw = override ? override.status : r.status
  const disp = displayStatus(statusRaw)
  return {
    ...r,
    disp,
    oos_progress: override ? override.oos_progress : oosProgressFromNotes(r.notes, r.wave),
    n: override ? override.n : (r.notes.match(/\bn\s*=\s*(\d+)/i)?.[1] ?? (r.notes.match(/N\s*=\s*(\d+)/)?.[1] ?? '—')),
    overridden: !!override,
    override_evidence: override ? override.evidence : null,
  }
})

const counts = rows.reduce((acc, r) => {
  acc[r.disp.key] = (acc[r.disp.key] || 0) + 1
  return acc
}, {})

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function badgeClass(key) {
  return `sb-badge sb-${key}`
}

const rowsHtml = rows.map((r) => `
        <tr>
          <!-- source: the vault/Reports/Signal Validation Scoreboard.md, section "${esc(r.section || '')}" -->
          <td class="sb-name"><code>${esc(r.signal_source)}</code><div class="sb-bot">${esc(r.owning_bot)}</div></td>
          <td><span class="${badgeClass(r.disp.key)}">${esc(r.disp.label)}</span>${r.overridden ? '<div class="sb-override-tag">live-reverified</div>' : ''}</td>
          <td class="sb-n">${esc(r.n)}</td>
          <td class="sb-oos">${esc(r.oos_progress)}</td>
          <td class="sb-notes">${esc(r.notes)}${r.overridden ? `<div class="sb-override-note"><strong>Override evidence:</strong> ${esc(r.override_evidence)}</div>` : ''}</td>
        </tr>`).join('\n')

const summaryHtml = Object.entries(counts)
  .sort((a, b) => b[1] - a[1])
  .map(([key, n]) => `<div class="stat"><div class="n">${n}</div><div class="l">${esc(displayStatusLabelForKey(key))}</div></div>`)
  .join('\n')

function displayStatusLabelForKey(key) {
  return { validated: 'VALIDATED', unvalidated: 'UNVALIDATED', pending: 'PENDING REPRO', removed: 'REMOVED (anti-edge)', thin: 'THIN-EDGE (capped)' }[key] || key
}

const dataSourceNote = vaultReadError
  ? `<p class="sb-error">Could not read the vault scoreboard (${esc(vaultReadError)}). This page could not be honestly regenerated — do not trust a stale copy below without checking the generation log.</p>`
  : `<p class="sb-source-note">Parsed live from <code>the vault/Reports/Signal Validation Scoreboard.md</code> (${rows.length} rows) at generation time ${esc(GENERATED_AT)}. 1 row live-reverified against current data during this run (see "live-reverified" tag below).</p>`

const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Scoreboard — every signal's validation status, in public</title>
  <meta name="description" content="Every signal in the fleet, its VALIDATED/UNVALIDATED/REMOVED status, and the citation behind it. Published before anything is sold — the same gate our own capital has to clear.">
  <link rel="canonical" href="https://jaimenbell.dev/scoreboard.html">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="MCP Integration Sprint">
  <meta property="og:title" content="The Scoreboard — every signal's validation status, in public">
  <meta property="og:description" content="Every signal in the fleet, its VALIDATED/UNVALIDATED/REMOVED status, and the citation behind it. Published before anything is sold.">
  <meta property="og:url" content="https://jaimenbell.dev/scoreboard.html">
  <meta property="og:image" content="https://jaimenbell.dev/img/og-card.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="jaimenbell.dev — Production MCP servers for AI agents">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="The Scoreboard — every signal's validation status, in public">
  <meta name="twitter:description" content="Every signal, its status, and the citation behind it. Published before anything is sold.">
  <meta name="twitter:image" content="https://jaimenbell.dev/img/og-card.png">
  <link rel="stylesheet" href="css/style.css">
  <style>
    /* Scoreboard-specific styling, scoped to this page — reuses the shared
       --bg/--card/--border/--accent tokens from css/style.css so it stays
       on the site's design language without new global rules. */
    .sb-wrap { overflow-x: auto; margin: 22px 0; border: 1px solid var(--border); border-radius: var(--radius); }
    table.sb { border-collapse: collapse; width: 100%; min-width: 760px; font-size: 0.9rem; }
    table.sb th { text-align: left; background: var(--bg-soft); color: var(--muted); font-weight: 600;
      font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; padding: 12px 14px; border-bottom: 1px solid var(--border); }
    table.sb td { padding: 12px 14px; border-bottom: 1px solid var(--border); vertical-align: top; color: var(--text); }
    table.sb tr:last-child td { border-bottom: none; }
    table.sb tr:hover td { background: rgba(255,255,255,0.02); }
    .sb-name code { font-family: var(--mono); color: var(--accent-2); font-size: 0.86em; }
    .sb-bot { color: var(--faint); font-size: 0.78rem; margin-top: 2px; }
    .sb-badge { display: inline-block; font-family: var(--mono); font-size: 0.72rem; font-weight: 700;
      padding: 3px 9px; border-radius: 999px; white-space: nowrap; letter-spacing: 0.02em; }
    .sb-validated { background: rgba(52,211,153,0.14); color: #34d399; border: 1px solid rgba(52,211,153,0.35); }
    .sb-unvalidated { background: rgba(159,176,201,0.12); color: var(--muted); border: 1px solid var(--border); }
    .sb-pending { background: rgba(251,191,36,0.12); color: #fbbf24; border: 1px solid rgba(251,191,36,0.35); }
    .sb-removed { background: rgba(248,113,113,0.12); color: #f87171; border: 1px solid rgba(248,113,113,0.35); }
    .sb-thin { background: rgba(91,157,255,0.12); color: var(--accent); border: 1px solid rgba(91,157,255,0.35); }
    .sb-override-tag { font-size: 0.68rem; color: var(--faint); margin-top: 4px; font-style: italic; }
    .sb-n { font-family: var(--mono); color: var(--muted); }
    .sb-oos { color: var(--muted); font-size: 0.85rem; max-width: 220px; }
    .sb-notes { color: var(--muted); font-size: 0.85rem; max-width: 340px; }
    .sb-override-note { margin-top: 8px; padding: 8px 10px; background: rgba(251,191,36,0.06); border-left: 2px solid #fbbf24; border-radius: 0 6px 6px 0; font-size: 0.82rem; color: var(--text); }
    .sb-source-note, .sb-error { color: var(--faint); font-size: 0.85rem; margin: 10px 0 0; }
    .sb-error { color: var(--warn); }
    .sb-legend { display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }
    .sb-freshness { margin: 22px 0; }
  </style>
</head>
<body>

<header class="site">
  <div class="wrap">
    <a class="brand" href="index.html" style="text-decoration:none">MCP<span class="dot">·</span>Engineering</a>
    <nav class="top">
      <a href="index.html#proof">Proof</a>
      <a href="index.html#offer">Offer</a>
      <a href="index.html#faq">FAQ</a>
      <a href="scoreboard.html"><strong>Scoreboard</strong></a>
      <a href="mailto:jaime@jaimenbell.dev">Contact</a>
    </nav>
  </div>
</header>

<section style="border-bottom:0">
  <div class="wrap">
    <article class="cs">
      <a class="back" href="index.html#cases">← Back to site</a>
      <h1>The Scoreboard</h1>
      <div class="meta">// every signal, its validation status, and the receipt behind it</div>

      <span class="pill">Holm + BH-FDR two-gate discipline</span>
      <span class="pill">same gate the paper-only fleet holds itself to</span>
      <span class="pill">${rows.length} rows tracked</span>

      <div class="honest">
        <p>
          <strong>The rule, up front:</strong> nothing gets marketed as accurate before this
          scoreboard says so, in public. The category this page sits in — signal
          services, whale-tracking feeds, alt-data alerts — mostly sells confidence without
          receipts. This is the receipts, published <em>before</em> anything is for sale.
          Today that mostly means <code>UNVALIDATED</code> and <code>INSUFFICIENT_DATA</code>
          rows below — that is the honest state of a young signal-validation campaign, and
          publishing it plainly (rather than hiding it behind marketing copy) is the actual
          product. One more honesty note: the whole fleet these signals come from trades
          <strong>paper money only</strong>, nothing live — see the
          <a href="case-studies/honest-harness.html">validation-harness case study</a> for that
          context.
        </p>
      </div>

      <h2>How a row gets promoted</h2>
      <p>
        A signal starts <code>UNVALIDATED</code> (weight zero, logged only). It is promoted to
        <code>VALIDATED</code> only after it survives a pre-registered backtest against a minimum
        out-of-sample window, Holm-corrected within its own test run <strong>and</strong>
        Benjamini-Hochberg FDR-corrected across the whole campaign (q=0.10) — the same two-gate
        discipline applied to every strategy before it is trusted with (paper) position sizing.
        A signal
        that backtests as anti-predictive is marked <code>REMOVED</code> (quarantined at weight
        zero) and requires a root-cause analysis before it can re-enter. A signal with a real but
        structurally small edge (e.g. compressed funding-rate arb spreads) is marked
        <code>THIN-EDGE</code> — capped, never allowed to solo-drive a decision, and that cap is
        not revisited by more data because it's a structural ceiling, not a sample-size problem.
        Validated rows still carry a decay clock: 90 days without a re-test demotes them back to
        <code>UNVALIDATED</code>.
      </p>

      <div class="proof sb-freshness">
        ${summaryHtml}
      </div>

      ${dataSourceNote}

      <div class="sb-wrap">
        <table class="sb">
          <thead>
            <tr>
              <th>Signal</th>
              <th>Status</th>
              <th>N</th>
              <th>OOS / wave progress</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}
          </tbody>
        </table>
      </div>

      <h2>What this page deliberately does NOT do</h2>
      <ul>
        <li>It does not round an <code>UNVALIDATED</code> row up to "promising" in the copy. If the table says unvalidated, the header text above says unvalidated too.</li>
        <li>It does not hide the one row (<code>whale-tracker.confluence</code>) whose earlier VALIDATED verdict was walked back after a methodology re-check found the result didn't reproduce under a second, independent statistical test. That reversal is the scoreboard working as intended, not a failure to hide.</li>
        <li>It does not backdate a graduation. Every VALIDATED row here still carries its 90-day decay clock and re-test requirement.</li>
      </ul>

      <p style="margin-top:32px">
        <a class="btn btn-primary" href="mailto:jaime@jaimenbell.dev?subject=Data%20feed%20scoreboard">Ask about the data feeds</a>
        &nbsp;<a class="btn btn-ghost" href="index.html#cases">← All case studies</a>
      </p>
    </article>
  </div>
</section>

<footer class="site">
  <div class="wrap">
    <span>MCP Server Engineering · auth-scoped, fail-soft, tested.</span>
    <span><a href="https://github.com/jaimenbell/MCP-Factory">GitHub</a> · <a href="mailto:jaime@jaimenbell.dev">jaime@jaimenbell.dev</a></span>
  </div>
</footer>

<!--
  GENERATION FINDINGS (regen instructions + instrumentation gaps for a future auto-version):

  One command regenerates this page:
    node scripts/generate-scoreboard.mjs

  What renders vs what's deferred:
  - All ${rows.length} rows render straight from the vault's own hand-maintained
    "Signal Validation Scoreboard.md" (the file's own frontmatter calls it the
    campaign's single source of truth). No status, wave, or note text is invented;
    every row keeps its section-of-origin as a source citation (see the HTML
    comment above each <tr>).
  - One row (whale-tracker.confluence) carries a LIVE override: this generator run
    re-executed research/whale_flow_check.py against the current
    whale-tracker/data/signal_log.jsonl and got a materially different verdict than
    the vault doc's last hand-edit (2026-05-21) reflects. That is disclosed inline,
    not silently substituted.
  - NOT built in this pass, and needed before this can regenerate unattended:
      1. whale_flow_check.py's own "SUMMARY FOR VAULT NOTE" block ends with THREE
         hardcoded literal strings ("45-day history", "~90 days (~2026-07-07)",
         "~300 days (~2027-01-31)") that do NOT recompute from the script's own
         n_days_history variable -- they were correct once and are now silently
         stale text sitting next to genuinely-recomputed numbers in the same
         printout. A future auto-version must fix this file to interpolate real
         values (or this generator will eventually cite a hardcoded lie next to a
         live one). Flagging this as the single highest-priority fix.
      2. No persisted JSON snapshot exists anywhere for the scoreboard -- the vault
         MD is hand-edited and whale_flow_check.py only prints to stdout. An
         auto-regen hook needs (a) whale_flow_check.py refactored to write a dated
         JSON artifact instead of print-only, and (b) the vault MD's own
         Update Protocol ("same-PR rule") extended to also regenerate this page in
         the same pass, so the public copy can never drift further behind the
         internal one than a single commit.
      3. No code anywhere currently re-verifies the vault MD table for internal
         consistency (row count, enum values) before this script trusts it -- a
         typo'd status cell would render silently. A lint pass belongs in the
         eventual auto-version, not hand-added here as a one-off.
      4. This script currently reads an ABSOLUTE machine path
         (C:\\Users\\jaime\\projects\\the vault\\...) for the vault note, matching
         the same pattern generate-og-image.mjs uses for a local Chrome binary.
         That is fine for a hand-run generator on this machine; it is NOT fine for
         a schtask-driven auto-regen without first deciding where the vault lives
         relative to whatever runs the schtask.
-->

</body>
</html>
`

fs.writeFileSync(OUT_HTML, html, 'utf-8')
console.log(`wrote ${OUT_HTML} (${rows.length} scoreboard rows, ${vaultReadError ? 'VAULT READ FAILED: ' + vaultReadError : 'vault read OK'})`)
