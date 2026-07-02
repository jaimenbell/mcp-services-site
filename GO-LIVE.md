# GO-LIVE runbook

Operator steps, in order. Every command block states its shell.

## 0. BLOCKER — resolve the two email leaks (LOCAL HALF DONE 2026-07-02 13:15)

Two git-state leaks of the personal address were found (a pushed branch with the address in
file contents, and gmail author metadata on main's two old commits). **The local remediation
is ALREADY DONE** — orchestrator squashed `main` to a single clean-author root commit
(`e3333e0`, noreply author, all current files); the old private history is preserved on the
LOCAL-ONLY branch `old-main-pre-squash` (**never push that branch** — it carries both leaks;
it exists purely as a rollback).

**Remaining = two remote operations (your hands, any shell):**
```bash
git -C C:/Users/jaime/projects/mcp-services-site push --force origin main
git -C C:/Users/jaime/projects/mcp-services-site push origin --delete chore/fill-live-placeholders
git -C C:/Users/jaime/projects/mcp-services-site branch -D chore/fill-live-placeholders
```

**Verify before flipping public (must show ONE commit, noreply author only):**
```bash
git -C C:/Users/jaime/projects/mcp-services-site fetch --prune
git -C C:/Users/jaime/projects/mcp-services-site log --format="%h %ae" origin/main
git -C C:/Users/jaime/projects/mcp-services-site branch -r
```

**Do not flip the repo public until the verify shows clean.**

## 1. Create the business email

Operator action outside this repo (~15:00 MT per plan). Have the address ready before step 2.

## 2. Run the swap (fills `[EMAIL]`, optionally repoints Calendly)

```bash
cd /c/Users/jaime/projects/mcp-services-site
python scripts/swap_email.py you@example.com
```

Optional — if using Calendly instead of `mailto:` for the 5 primary "Book a scoping call"
buttons (nav/footer Contact links stay `mailto:` either way):
```bash
python scripts/swap_email.py you@example.com --calendly https://calendly.com/you/scoping-call
```

The script is count-verified: it prints per-file replacement counts, refuses to report success
on a no-op (0 placeholders found), and re-scans after writing to confirm 0 `[EMAIL]` remain. Add
`--dry-run` first if you want to preview with zero writes.

## 3. Review the diff

```bash
git diff
```
Confirm: no stray `[EMAIL]` left, the address is spelled correctly everywhere, Calendly hrefs (if
used) only touched the 5 "Book a scoping call" buttons and not the nav/footer Contact links.

## 4. Commit

```bash
git add -A
git commit -m "chore: fill live contact address"
```

## 5. Flip the repo public

GitHub → repo → Settings → General → Danger Zone → **Change visibility → Public**. Operator hands
per the task brief.

## 6. Enable GitHub Pages

Settings → Pages → Source = *Deploy from a branch* → Branch = `main` / `/ (root)` → Save. Live in
~1 minute at `https://jaimenbell.github.io/mcp-services-site/`.

## 7. Push

```bash
git push origin main
```
(If you deleted `chore/fill-live-placeholders` in step 0, that push already happened separately.)

## 8. Verify live

- Load `https://jaimenbell.github.io/mcp-services-site/` — hero, proof stats (179 / 50), offer
  tiers, case studies, FAQ all render.
- Load a non-existent path (e.g. `.../nope`) — confirm the custom `404.html` shows, not GitHub's
  default 404.
- Click through to each of the 3 case studies from `#cases` and back via "All case studies".
- Click "Book a scoping call" from the hero, the offer tier, and the CTA band — confirm it opens
  either the mail client with the right address + subject, or the Calendly page if that path was
  used.
- Click the footer "Contact" link and the footer email text link — same check.
- Confirm the "179 passing tests" / "mcp-factory" and "50 tests" / "rag-mcp" links resolve to the
  public repos.

## Notes for future updates

- Test counts (179 mcp-factory, 50 rag-mcp, 186 options-bot) were live-verified today
  (2026-07-02) by running each suite in its own repo's venv — not copied from an old claim. If
  either upstream repo's suite grows/shrinks, re-run and re-grep this site for the stale number
  before it goes stale again.
- `[SITE_URL]` is already resolved to `https://jaimenbell.github.io/mcp-services-site` (GitHub
  Pages URL is deterministic from repo name) — only `[EMAIL]` remains as a placeholder.
