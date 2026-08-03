# mcp-services-site

Public marketing site for a productized **Model Context Protocol (MCP) server** engineering
service — landing page, fixed-scope offer, and three honest, verifiable case studies. Static
HTML/CSS, no backend, deployable free on GitHub Pages.

## What's here

```
index.html                         landing page (hero, proof, offer, process, FAQ, CTA)
css/style.css                      single stylesheet (no frameworks, no build step)
case-studies/mcp-factory.html      case study 1 — manifest-driven MCP scaffolder (233 tests, public + Loom)
case-studies/rag-mcp.html          case study 2 — RAG retrieval MCP (149 tests, local/$0)
case-studies/honest-harness.html   case study 3 — honest validation harness (rigor, not returns)
404.html                           GitHub Pages custom 404 (no build step needed for this to work)
scripts/swap_email.py              one-shot jaime@jaimenbell.dev -> real address swap (+ optional Calendly)
scripts/generate_self_audit_table.py  regenerates the dogfood self-audit block on
                                    articles/fleet-audit-methodology.html from a live run --
                                    see "Dev setup" below, never hand-edit that block
.nojekyll                          tells GitHub Pages to serve files as-is (no Jekyll processing)
```

## Placeholders the operator fills before going live

`[SITE_URL]` is already filled in (`https://jaimenbell.github.io/mcp-services-site`) since the
GitHub Pages URL is deterministic from the repo name. The one remaining placeholder is `jaime@jaimenbell.dev`
(21 occurrences across index.html, 404.html, the 3 case studies, and this README) — every
`mailto:` + CTA.

Run the one-shot swap script once the real contact address exists:

```
python scripts/swap_email.py you@example.com
```

It replaces every `jaime@jaimenbell.dev` occurrence and prints a before/after count so the swap is verified,
not assumed. Pass `--calendly https://calendly.com/you/scoping-call` in the same command to also
point the 5 primary **"Book a scoping call"** buttons at Calendly instead of `mailto:` (the nav
and footer contact links stay `mailto:` either way). See `--help` for `--dry-run`.

Quick check for anything left unfilled:

```
grep -rn "\[EMAIL\]" .
```

## Honesty contract (do not break)

This is a public asset with our name on it. Every number is real and checkable:

- **mcp-factory — 233 passing tests**, public repo + 90-second Loom demo.
- **rag-mcp — 149 tests**, local ONNX (bge-large) embeddings, $0 inference cost.
- The fleet section sells **engineering rigor, not trading performance**. It states plainly that
  strategies that don't clear costs are killed (e.g. one bot retired at **−$735.66 over 1,002
  trades**). **No returns, profit, or gains are claimed anywhere** — by design.

Pricing tiers are **PROPOSED** and labeled as such on the page. Confirm them before quoting clients.

## Host on GitHub Pages (free, ~3 min)

1. Create a new public GitHub repo named `mcp-services-site`.
2. Push this folder:
   ```
   git remote add origin https://github.com/<your-username>/mcp-services-site.git
   git push -u origin main
   ```
3. Repo → **Settings → Pages** → Source = *Deploy from a branch* → Branch = `main` / `/ (root)` → **Save**.
4. After ~1 min the site is live at:
   `https://jaimenbell.github.io/mcp-services-site/`
5. Run `python scripts/swap_email.py <address>` to fill `jaime@jaimenbell.dev`, review the diff, commit, push.

> A custom domain can be added later under **Pages → Custom domain**; the `github.io` URL works fine.

## Local preview

Open `index.html` directly in a browser, or serve the folder:

```
python -m http.server 8000   # then visit http://localhost:8000
```

## Dev setup — proof-number gate

This repo enforces a commit-time gate against proof-number drift (a cited test count going
stale relative to reality — see `proof-manifest.toml` and `scripts/check_proof_numbers.py`).
Enable it once per clone:

```
git config core.hooksPath .githooks
```

`.githooks/pre-commit` is committed with its executable bit set (mode 100755), so this one-line
`core.hooksPath` config is all that's needed on Linux/macOS. If a checkout ever loses the exec bit
(e.g. some non-git file transfer), restore it with `git update-index --chmod=+x .githooks/pre-commit`.

Tests: `pip install -r requirements-dev.txt` then `python -m pytest` (see `pytest.ini`).

## Dev setup — regenerating the dogfood self-audit block

`articles/fleet-audit-methodology.html` embeds a worked example of running
[mcp-security-scanner](https://github.com/jaimenbell/mcp-security-scanner)'s
`--self-audit` against the fleet of MCP servers this site sells (which server
is clean, which has findings, per-server P1 counts and finding descriptions).
That content sits between `<!-- SELF-AUDIT-AUTOGEN:START -->` /
`<!-- SELF-AUDIT-AUTOGEN:END -->` markers and **must never be hand-edited** --
it goes stale the same way a hardcoded test count does the moment any fleet
server's audit status changes. Regenerate it instead:

```
# PowerShell
$env:MCP_SCANNER_FLEET_ROOT = "C:\Users\you\projects"   # dir containing your fleet repos
python scripts/generate_self_audit_table.py               # writes the file if data changed
python scripts/generate_self_audit_table.py --check        # dry run, exit 1 if stale
```

It runs `mcp-scan --self-audit --json` live in your local
`mcp-security-scanner` checkout (default: a sibling `../mcp-security-scanner`
directory next to this repo; override with `MCP_SCANNER_REPO`) and rewrites
the marker region from the real result -- verdict, P1 counts, and the actual
finding titles, not typed prose. Review the diff and commit like any other
change. This is not yet wired into the pre-commit gate (`check_proof_numbers.py`
only covers numeric test-count citations); running it is a manual step for now
whenever the fleet's audit posture might have moved.

## License / status

Private marketing asset. Pricing is proposed pending operator confirmation; case-study numbers are
re-verified against live test-suite runs (last verified 2026-07-02).
