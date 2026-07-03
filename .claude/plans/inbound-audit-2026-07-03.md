---
title: inbound-seo-audit-2026-07-03
tags: [context/seo, context/site, context/audit]
date created: 2026-07-03
---

# Inbound SEO / conversion audit — jaimenbell.dev (2026-07-03)

> [!note] Scope
> Lane `inbound-seo-audit`, contract §R (read-audit) + §S (research) + §X. One findings doc +
> the small additive fixes explicitly allowed (missing meta/OG/sitemap/robots — zero design
> risk). Branch `site/inbound-tuning`, commit `2022a72`, based on `main` @ `b1403db`.

## TL;DR

The site went live **one day ago** (2026-07-02) and is **not indexed anywhere yet** —
`site:jaimenbell.dev` returns zero Google results. That's expected at T+1 day, but three real
bugs were compounding the delay: canonical/OG tags on every page pointed at a dead alias domain,
there was no sitemap.xml or robots.txt to accelerate discovery, and case-study pages (the most
shareable "proof" content) had zero Open Graph tags, so links shared in DMs/LinkedIn render as
bare text. All three are fixed on `site/inbound-tuning`. The bigger, structural gap — no
lead-capture for a visitor who isn't ready to email right now — is findings-only; it needs a
judgment call about adding a third-party form service to an intentionally-static site.

## Evidence table

| # | Claim | Evidence | Status |
|---|---|---|---|
| 1 | Canonical + og:url on every page pointed at `jaimenbell.github.io/mcp-services-site`, not the live `jaimenbell.dev` | `index.html:10,16` (pre-fix), all 5 `case-studies/*.html:8`, `404.html:8` (pre-fix); confirmed via `grep -rn jaimenbell.github.io` before the fix | FIXED (branch `site/inbound-tuning`) |
| 2 | The mismatch is a real regression, not a stale README | `git log --oneline -- CNAME`: CNAME (custom domain) was added in `8511d30` (2026-07-02 20:39), **after** the GO-LIVE commit `edf6887` that stamped canonical URLs to the github.io alias — nobody re-swept canonical/OG after the domain move | KNOWN-FRESH bug, verified via git history |
| 3 | `jaimenbell.github.io/mcp-services-site/` correctly 301s to `https://jaimenbell.dev/` | WebFetch of the github.io URL returned `301 Moved Permanently` → `jaimenbell.dev` | No duplicate-content crawl risk from GitHub Pages itself — the canonical bug was purely a stale-tag issue, not a live redirect loop |
| 4 | robots.txt and sitemap.xml were both absent | `find . -iname robots.txt -o -iname sitemap*.xml` in repo: no matches; WebFetch `https://jaimenbell.dev/robots.txt` and `/sitemap.xml`: both HTTP 404 | FIXED — added `robots.txt` (Allow: / + sitemap pointer) and `sitemap.xml` (7 URLs, index + 6 case studies) on the branch |
| 5 | No structured data (JSON-LD) anywhere on the site | `grep -rn "application/ld+json"` across repo: 0 matches | FINDINGS-ONLY (see P2 below — deliberately not added; see rationale) |
| 6 | No `og:image` / social preview image anywhere; site has zero `<img>` tags (pure CSS/canvas art, no bitmap assets) | `grep -rn "<img "` across repo: 0 matches; index.html/case-study heads have no `og:image` | FINDINGS-ONLY — needs a real designed asset, out of scope for a zero-design-risk fix |
| 7 | Case-study pages had **zero** Open Graph / Twitter Card tags (only title/meta description/canonical) | Read of all 6 `case-studies/*.html` heads pre-fix: no `og:` or `twitter:` properties present | FIXED — added matching og:title/description/url/type + twitter:card to all 5 case studies |
| 8 | Site is not indexed by Google as of 2026-07-03 | `WebSearch site:jaimenbell.dev` → 0 relevant results (returned an unrelated `jaimyn.dev` blog instead); `WebSearch "jaimenbell.dev MCP"` → 0 relevant results | Expected at T+1 day post-launch; no Search Console evidence found or claimed (none set up) |
| 9 | Inbound entry surface (MCP-Factory README) does link to the live domain correctly | WebFetch of `github.com/jaimenbell/MCP-Factory` README: *"Maintained by Jaimen Bell. For production MCP integrations, custom servers, or agent-reliability work, see jaimenbell.dev..."* | GOOD — the entry link itself is correct and points at the site root, not a dead path |
| 10 | Every CTA on the site is a raw `mailto:` link; zero email-capture / newsletter / form | `grep -n "mailto:jaime@jaimenbell.dev" index.html`: 8 occurrences, all CTAs; no `<form>`, no Calendly link wired (GO-LIVE.md documents Calendly as an unused optional path) | FINDINGS-ONLY — see P1 below |
| 11 | Homepage has no build step, no external JS beyond Google Fonts preconnect, no images — page is 90KB inline HTML + 9KB CSS, 2 inline `<script>` blocks gated by IntersectionObserver | `wc -c index.html css/style.css` = 90282 + 8929 bytes; `grep -c "<script"` = 2, both inline, no `src=` script tags found | Reasonably lean for a static site; not a real perf bottleneck given 0 image weight |
| 12 | LinkedIn as an entry surface — unverified | No LinkedIn profile URL was available to check in this audit | NEEDS-CHECK — operator item, not verifiable from this lane |

## Findings, ranked

### P0 — none remaining
The one true P0 (canonical/OG pointing at the wrong domain on every single page, a week-one
indexing-signal bug) is fixed on the branch.

### P1 — high leverage, needs an operator decision (not a zero-risk static-site fix)

1. **No lead capture for a "not ready to email yet" visitor.** Every single CTA is `mailto:`.
   That's fine for someone who already decided to hire you, but it loses everyone in
   "interested, not ready" mode — the majority of first-time visitors from a cold registry/README
   link. Options, honestly:
   - **Cheapest / zero backend**: a `mailto:` is what you already have — no change needed if the
     target audience really is "ready-to-buy engineers reading a README," which is plausible here.
   - **Lightweight capture with a static site**: Formspree, Buttondown, or a Google Form embed —
     each needs a 3rd-party account + a small JS/HTML snippet, but no backend/hosting change.
     This is a real code change with a design decision (where does the form go, what does it say)
     — bigger than "additive, zero design risk," so it's not applied here.
   - **Do nothing**: also a legitimate call if the retainer/sprint offer is deliberately
     high-touch and low-volume; a hastily bolted-on newsletter form can look worse than none.
   Recommendation: decide this explicitly rather than by default. Effort: S (Formspree) to M
   (design + copy for a real capture flow).

2. **Set up Google Search Console + submit the new sitemap.** The site has no verified GSC
   property (no evidence found of one). Effort: S, but requires operator hands (DNS TXT record
   or HTML file verification) — paste-steps below.

3. **Get external backlinks flowing.** The MCP-Factory README already links out correctly (#9
   above) — verify the other 3 MCP Registry listings + PyPI package pages do the same (this lane
   could not access the MCP registry listing content directly; spot-check via the registry site
   or PyPI project pages). Each verified inbound link from an indexed page is worth more than any
   on-page tweak at this stage — Google has nothing to crawl from yet.

### P2 — real gaps, lower urgency

4. **No structured data (JSON-LD).** Adding `ProfessionalService` schema could help rich results
   later, but doing it wrong (mismatched fields, wrong type) is worse than not doing it — treated
   as findings-only rather than a "zero design risk" fix. If picked up later: `ProfessionalService`
   or `Organization` type, `name`, `url: https://jaimenbell.dev/`, `sameAs` for GitHub, `areaServed`,
   no fabricated `aggregateRating`/`review` (would violate the site's own honesty contract).

5. **No `og:image`.** Every shared link (Slack/LinkedIn/X) renders as text-only. The site has zero
   bitmap assets by design (pure CSS/canvas). A designed 1200×630 OG card is a real design task —
   findings-only.

6. **`fleet-reliability-day.html`'s OG title/description were shortened from its very long
   `<title>`/meta description** (both fixed-length-friendly versions were substituted for the OG
   tags added in this pass, since the original title is 140+ characters — too long for a link
   preview card). Worth a human pass to confirm the shortened OG copy still reads well; not
   re-verified against brand voice beyond factual accuracy.

### P3 — keyword/positioning (context, not urgent)

7. **SERP scan for "MCP integration consultant" / "custom MCP server development"**: top-10
   results are all agencies/platforms (Intuz, mcp-agency.com, Composio, Salesforce, SnapLogic) —
   no indie/solo consultant visible. **Gap exists and is winnable** once indexed — nobody owns
   "solo engineer, public proof, fixed-scope sprint" positioning in the visible SERP today.
8. **SERP scan for "AI agent reliability testing consultant"**: dominated by enterprise eval
   platforms (Openlayer, Maxim, Galileo) and staffing marketplaces (Upwork/Toptal) — same
   pattern, same opportunity, same indexing blocker.
9. Both scans are moot until indexing happens (P1.2/P1.3) — positioning quality doesn't matter if
   the page isn't in the index yet.

## What a static site honestly can't do

- No server-side redirects beyond what GitHub Pages + the CNAME already provide.
- No analytics/conversion tracking without adding a 3rd-party script (privacy/perf tradeoff —
  not recommended by default; flag if the operator wants visit data).
- No dynamic sitemap regeneration — `sitemap.xml` added here is hand-maintained; add a new
  `<url>` block manually any time a new case study ships (case-studies grow at roughly 1/week
  per recent git history).
- No form backend — any lead-capture beyond `mailto:` requires an external service (Formspree,
  Buttondown, Google Forms) since there is no server to receive a POST.

## Operator paste-items

### 1. Google Search Console setup (manual, ~10 min)

```text
1. Go to https://search.google.com/search-console
2. Add property: "jaimenbell.dev" (Domain property, not URL-prefix, so it covers both
   the apex and any future subdomains)
3. Verify via DNS: Search Console gives you a TXT record value.
   Add it in Cloudflare (the registrar per GO-LIVE.md): DNS -> Add record -> TXT ->
   name "@" -> the value Search Console gave you -> Save.
4. Back in Search Console, click Verify (DNS propagation can take a few minutes).
5. Once verified: Sitemaps (left nav) -> Add a new sitemap -> enter "sitemap.xml" -> Submit.
   (This only works after the site/inbound-tuning branch's sitemap.xml is merged and deployed.)
```

### 2. Spot-check the other 3 MCP Registry listings + PyPI pages link to jaimenbell.dev

Not verified in this lane (no direct registry access). Quick manual check: open each of the
4 MCP Registry listings (mcp-factory, rag-mcp, github-mcp, desktop-mcp) and confirm the listing
page or its linked README shows the `jaimenbell.dev` link the way MCP-Factory's README does
(confirmed good, evidence #9 above).

## Fixes applied vs findings-only (summary)

| Fix | Applied? |
|---|---|
| Canonical + og:url corrected to `jaimenbell.dev` (index, 404, all 5 case studies) | Applied |
| robots.txt added | Applied |
| sitemap.xml added (7 URLs) | Applied |
| OG + Twitter Card tags added to all 5 case-study pages | Applied |
| Lead-capture / email list | Findings-only — needs operator decision + 3rd-party service |
| JSON-LD structured data | Findings-only — risk of getting schema wrong outweighs a rushed add |
| og:image / social card asset | Findings-only — needs a real design asset |
| Google Search Console | Findings-only — operator-hands DNS/verification step, paste-steps above |
| Registry listing spot-check | Findings-only — no direct access from this lane |
