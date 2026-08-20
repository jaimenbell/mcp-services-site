---
title: Site Instrumentation Setup
status: wired — analytics and booking both live as of 2026-08-20
created: 2026-07-22
updated: 2026-08-20
tags: [site, analytics, booking, instrumentation]
---

# Site Instrumentation Setup

> [!important] Both placeholders are filled. This doc is now a record, not a to-do.
> Analytics (GoatCounter) and the booking CTA (cal.com) are both wired and deployed.
> What follows documents what is wired, the coverage rule new pages must follow, and how to
> verify instrumentation honestly. If you are adding a page, read **Coverage rule** below.

## Analytics — GoatCounter (wired 2026-08-20)

**Why GoatCounter:** free hosted, **no cookies**, no consent banner required, no cross-site
tracking, single async `<script>` tag, **$0 infra**. Plausible was the alternative but its hosted
tier is paid and self-hosting needs a server.

**Site code:** `jaimenbell` → dashboard at `https://jaimenbell.goatcounter.com`.

Every user-facing page carries this tag immediately before `</head>`:

```html
<script data-goatcounter="https://jaimenbell.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```

## Booking — cal.com (wired)

**Handle:** `jaimen-bell-ioj5i8` → `https://cal.com/jaimen-bell-ioj5i8`.

Note the handle is **not** a tidy vanity string; do not retype it from memory, copy it. The
"Book a scoping call" buttons carry it. The existing `mailto:jaime@jaimenbell.dev` primary buttons
are **kept as the no-tooling fallback** — booking is additive, not a replacement.

## Coverage rule — read this before adding a page

**Every user-facing `.html` page carries exactly one `data-goatcounter` tag.** Not most pages, not
the important ones: every one. Deliberate exclusions, and the only ones:

| Path | Why excluded |
|---|---|
| `scripts/og-card.html` | generator template, never served to a visitor |
| `.claude/worktrees/**` | throwaway worktrees, not the deployed site |

⚠ **`scoreboard.html` is GENERATED** by `scripts/generate-scoreboard.mjs`. Its beacon lives in the
generator's `<head>` template, not only in the output file. Editing `scoreboard.html` by hand is
silently reverted on the next generator run — change the producer, then regenerate.

### Why the rule is stated this way

On 2026-08-20 the tag covered 16 of 26 user-facing pages. The gap included
`case-studies/mcp-security-scanner.html` — the landing page the published LinkedIn piece links to.
The analytics install was green and working, and **structurally incapable of measuring the one page
traffic was being driven to.** A zero would have read as "nobody clicked" when it actually meant
"nothing was ever counted."

The original gap was not carelessness: three flagship case studies were authored on a different
branch (`lane/flagship-coverage`) than the instrumentation (`lane/site-instrumentation`), so they
were never in the instrumenting branch's base. `404.html` and `scoreboard.html` were consciously
skipped. The lesson is that a coverage rule with no enforcement decays at every branch merge — so
state the scope with the pattern, and check it.

## Verifying instrumentation honestly

**A 200 from the beacon request is send-side bookkeeping. It does not prove a hit was recorded.**
Verify from the receiving end:

1. Load a page on the live site.
2. Confirm the pageview appears at `https://jaimenbell.goatcounter.com` within seconds.

Until a hit is visible in the dashboard, the instrumentation is unproven — a wrong site code fails
**silently**: the beacon 404s with no JS error, no console noise, and no page impact, so the site
looks perfectly healthy while recording nothing.

⚠ When verifying a fresh deploy, use `curl` with a cache-buster rather than a caching fetcher — a
15-minute URL cache will serve the pre-deploy page and look like a failed deploy.

For booking: click "Book a scoping call" on the live site → it should open the cal.com page. A wrong
handle gives cal.com's 404, not a broken site.

## CSP note

No Content-Security-Policy is set on this site (no CSP `<meta>` tag; GitHub Pages sets no CSP
header) — so **no allowlist edit is needed** for the analytics script to run. If you ever add a CSP,
allowlist: `script-src //gc.zgo.at` and `img-src`/`connect-src https://*.goatcounter.com`.
