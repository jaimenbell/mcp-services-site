---
name: port-sprint-landing-design
created: 2026-07-02
goal: Make jaimenbell.dev look like the original mcp-sprint-landing page — port that richer design as the new index.html, merging in the live site's real content (case studies, FAQ, live contact, current proof numbers)
acceptance_criteria:
  - new index.html is the landing-derived rich page (>= 1000 lines, hero/problem/deliver/proof/process/pricing/contact sections present)
  - no contact placeholder remains; jaime@jaimenbell.dev wired in >= 3 spots including the CTA
  - proof numbers current (156 for mcp-factory, zero occurrences of 152); per-repo numbers match the case-study pages
  - all 5 case-study pages linked from index and their files untouched
  - FAQ section preserved
  - page renders correctly in a real browser (screenshot evidence), CNAME/404 untouched
iteration_budget:
  max_turns: 18
  max_tokens: 180000
executor_model: sonnet
parallel_safe: false
risk_level: low
escalate_on:
  - budget_exhausted
  - stuck_3_turns
  - any_push_attempt
linked_memory:
  - mcp-services-site-live
  - freelance-offer-1-mcp-services
---

# SITE — port the mcp-sprint-landing design onto jaimenbell.dev

## Context
Operator directive 2026-07-02 night: the original landing page (C:\Users\jaime\projects\mcp-sprint-landing\index.html, 1368 lines, self-contained inline-CSS/JS + Google Fonts, built 2026-06-23 with full honesty rails — see its NOTES.md) looks far better than the live 252-line index at C:\Users\jaime\projects\mcp-services-site. "Our domain should be just like the landing page." The live site (GitHub Pages, CNAME jaimenbell.dev) has real content the landing predates: 5 case studies (mcp-factory, rag-mcp, honest-harness, github-mcp, desktop-mcp), an FAQ, live contact jaime@jaimenbell.dev (7 spots), and the CURRENT proof number 156 (landing hardcodes 152 in ~8 spots incl. the stat band). Verified live 2026-07-02 ~21:15 MT. Lane contract: `~/.claude/lane-contracts.md` §W.

## Approach
Landing page = design base; live site = content truth. Copy the landing index.html into mcp-services-site as the new index, then: fill its deliberate `contact-placeholder` block with the live mailto CTA pattern, update every proof number to current truth (156; per-repo counts exactly as each case-study page states them), graft in a case-studies section (proof-ladder) linking the 5 existing pages in the landing's visual language, carry over the FAQ section restyled to match, and keep head metadata (title/OG/description) at least as good as the live page's. Keep the page self-contained (inline CSS/JS; the Google Fonts link is fine on Pages). Do not touch case-studies/*.html, css/ (used by case-study pages), CNAME, or 404.html. The landing's `agent-session` terminal box is JS-animated — verify it actually plays in-browser; if it renders as a dead empty box, fix or cut it (an empty box reads broken).

## Steps
1. Read mcp-sprint-landing/index.html fully + its NOTES.md (honesty provenance) + the current live index.html (content inventory: case-study links/copy, FAQ items, contact wiring, footer).
2. Write the new index.html: landing design + merged content per Approach. Update stat band (152 -> 156), contact placeholder -> jaime@jaimenbell.dev mailto (subject-tagged like the live CTAs), add proof-ladder/case-studies section (5 links + one-line honest summaries), port FAQ, reconcile pricing copy with the live offer section (scoping-gated "from $5,000" framing stays).
3. Honesty pass: no fabricated testimonials (keep "first client case studies" honesty or point at the real case studies instead), mcp-factory = scaffold framing (never "generates the server"), no trading language, every number checkable against a public repo or case-study page.
4. Render file:///C:/Users/jaime/projects/mcp-services-site/index.html in a real browser (load browser tools via ToolSearch, or desktop-mcp screenshot fallback); screenshot desktop + a narrow-viewport check; verify hero, nav anchors, animations, and the agent-session box all render; fix what doesn't.
5. Run all acceptance Verify commands; commit on a branch `site/port-sprint-landing` with the old index preserved in git history. Do NOT push (operator pushes; Pages deploys from the repo).

## Acceptance tests
- Criterion: rich landing-derived index
  - Verify: `[ $(wc -l < index.html) -ge 1000 ] && grep -q 'id="pricing"' index.html && grep -q 'id="process"' index.html && echo RICH-OK` # expected_to_fail_until_impl (252 lines now)
- Criterion: contact wired, no placeholder
  - Verify: `! grep -q "contact-placeholder" index.html && [ $(grep -c "jaime@jaimenbell.dev" index.html) -ge 3 ] && echo CONTACT-OK` # pre-existing pass (must still pass after port)
- Criterion: proof numbers current
  - Verify: `! grep -q "152" index.html && grep -q "156" index.html && echo PROOF-OK` # expected_to_fail_until_impl
- Criterion: 5 case studies linked, files untouched
  - Verify: `ok=1; for f in case-studies/*.html; do grep -q "$(basename $f)" index.html || ok=0; done; [ $ok -eq 1 ] && git diff --quiet case-studies/ && echo CASES-OK` # pre-existing pass (must hold)
- Criterion: FAQ preserved
  - Verify: `grep -qi "faq" index.html && echo FAQ-OK` # pre-existing pass (must hold)
- Criterion: renders in browser
  - Verify: screenshot file exists and lane report includes it # manual-evidence criterion

## Out of scope
- Pushing / deploying (operator-only; Pages auto-deploys on push).
- Editing case-study pages, CNAME, 404.html, or the mcp-sprint-landing source folder (read-only reference).
- New copywriting beyond the merge (the landing copy is already rubric-polished).

## Open questions
- Landing hero says "50 / 50 paid on signature & acceptance" — confirm this matches the current offer framing (live site uses scoping-gated pricing); keep whichever the live offer section states if they conflict.
