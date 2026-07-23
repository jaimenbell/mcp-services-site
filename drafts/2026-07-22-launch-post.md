# Launch post drafts — Exit Strategy Portal (2026-07-22)

Status when drafted: portal launched TONIGHT in **test mode** (E2E proven,
30-min operator go-live path staged, gate = credentials only). It is **NOT
yet publicly purchasable** — do not post either variant below until the
go-live ceremony happens and a real signup/checkout link exists. The
`[SIGNUP LINK]` placeholder marks the one thing that must be filled in
before this goes out; everything else is already true as written.

Every factual claim below was verified against real repo state on
2026-07-22 before drafting:
- Portal launch (test mode, E2E proven): memory `exit-strategy-portal-shipped`
  — master `e78a562`, `docs/LAUNCH-CHECKLIST-30MIN.md` + `.env.template`.
- The kill-verdict: `the vault/research/2026-07-22 Edge-Hypothesis Survey
  (night session).md`, "V2 — BTC 15m turn-of-candle persistence" section —
  2024-2026 Binance BTCUSDT 1m klines, **2.36M bars**, 54 monthly archives,
  checksum-verified, $0 cost. Boundary-minus-interior edge = 0.028 bps, 95%
  block-bootstrap CI **[-0.034, +0.090] bps — includes 0**. Verdict:
  **KILL-falsifier**, same night as the portal launch. Branch
  `lane/v2-turn-of-candle` in `updown-collector`, SHA `90363c3`
  (uncommitted to master at time of writing — the finding is real; the merge
  is a separate housekeeping step).

---

## LinkedIn (long form)

Tonight I launched something and killed something, on the same night, and
I want to talk about the second one.

The launch: the Exit Strategy Portal — a $9/mo membership for people who
want to watch an engineering process happen in real time instead of reading
a highlight reel. Daily build-log, weekly fleet report card, member
digests. It's live in test mode right now while I finish the go-live
checklist; the public signup opens soon. [SIGNUP LINK]

The kill: a few hours after wiring up the launch, the same validation
harness that gates everything I ship ran its scheduled check on a trading
hypothesis I'd been sitting on — a "price momentum persists right at the
15-minute candle boundary" pattern with real academic backing from 2021.
I pulled 2.36 million 1-minute BTC bars from 2024-2026, checksum-verified,
cost $0 to test. The effect that was there in 2021 is gone: 0.028 bps,
confidence interval crosses zero. Not "inconclusive" — a clean,
pre-registered KILL.

That's the actual product. Not the portal, not any one trading system —
the discipline that makes me write "KILL" on my own idea instead of
quietly deleting the branch and never mentioning it existed. If you
subscribe to the membership, this is what you're actually paying for:
every hypothesis that doesn't survive gets a public verdict, the same
night it happens, whether or not it's flattering.

No trading advice here, ever — this is a record of engineering process,
not a signals service. If "show your work, including the failures" sounds
like a community worth being in, the site's below.

[SIGNUP LINK]

---

## X / short form

Launched a $9/mo build-in-public membership tonight (test mode, opening
soon). Same night, our validation harness killed one of our own trading
hypotheses on 2.36M price bars — clean CI crossing zero, no fudging.

That honesty is the actual product. [SIGNUP LINK]
