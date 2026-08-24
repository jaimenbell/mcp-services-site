# Deploying the click-beacon Worker

Turns the currently-inert `?ref=` click-attribution path (`js/click-track.js`)
into a working one. Nothing here is done automatically -- account/service
creation is deliberately outside what an unattended build step should do
(see `scripts/click-beacon-worker.example.js`'s own header). This is the
copy-paste path for a human to run it once.

**Cost: $0.** Cloudflare Workers free tier (100k requests/day, no card
required) is far more than this site's traffic needs.

## What you need first

- A free Cloudflare account (cloudflare.com -- sign-up only, no card).
- Node.js (for `npx wrangler`) -- already required to run
  `scripts/generate-scoreboard.mjs` in this repo, so if that already works
  here, you have it.

## Steps

### 1. Log in to Wrangler

```
npx wrangler login
```

Opens a browser tab to authorize the CLI against your Cloudflare account.
One-time per machine.

### 2. Create the KV namespace

```
npx wrangler kv namespace create CLICKS
```

Prints something like:

```
{ binding = "CLICKS", id = "a1b2c3d4e5f6..." }
```

Copy the `id` value -- you need it in step 3.

### 3. Stage the worker + config in a scratch directory

This repo does not check in a live `wrangler.toml` (Workers deploy is
outside this site's own build/deploy pipeline), so stage the two files
somewhere outside version control, e.g.:

```
mkdir C:\Users\<you>\scratch\click-beacon-deploy
copy scripts\click-beacon-worker.example.js C:\Users\<you>\scratch\click-beacon-deploy\click-beacon-worker.js
copy scripts\click-beacon-wrangler.toml.example C:\Users\<you>\scratch\click-beacon-deploy\wrangler.toml
```

Edit the copied `wrangler.toml`:
- Set `id = "..."` under `[[kv_namespaces]]` to the id from step 2.
- Leave `name`, `main`, `binding` as-is unless you have a reason to change
  them (the worker code reads `env.CLICKS`, which must match `binding`).

### 4. Deploy

```
cd C:\Users\<you>\scratch\click-beacon-deploy
npx wrangler deploy
```

Prints the deployed URL on success, shaped like:

```
https://click-beacon.<your-subdomain>.workers.dev
```

That subdomain is assigned once per Cloudflare account the first time you
deploy any Worker -- it stays the same for future deploys/updates.

### 5. Wire the URL into this repo -- the one line

Open `js/click-track.js` and replace line 27:

```js
var CLICK_BEACON_URL = ""; // e.g. https://click-beacon.<you>.workers.dev -- set once deployed
```

with the deployed URL from step 4:

```js
var CLICK_BEACON_URL = "https://click-beacon.<your-subdomain>.workers.dev";
```

That is the entire wiring step -- one line, one file. Commit and push (push
to this repo is a live deploy of the site, per repo convention) once you've
verified receipt below.

## Verifying receipt -- from the RECEIVING end, not a 2xx

`sendBeacon`/`fetch` returning success only proves the browser *sent*
something; it says nothing about whether the Worker received or stored it
(the send side is bookkeeping, not proof of delivery). Verify from the
Worker's own side instead:

### Live tail while you click a tracked link

```
npx wrangler tail click-beacon
```

Leave this running, then visit a URL on the deployed site carrying `?ref=`,
e.g. `https://<your-site>/?ref=abc123`. A live request log line should
appear in the `wrangler tail` output within a few seconds, showing the
incoming POST.

**The ref must be lowercase hex, 6-64 characters** (`[0-9a-f]{6,64}`) --
that's what `linktrack.make_ref()` in sales-reps actually generates, and
it's also what `click-beacon-worker.example.js` validates before writing
anything to KV (see its `ref` check). A non-hex test value (letters like
`g`-`z`, or anything shorter than 6 chars) is silently accepted with a 204
and never written to KV -- not a bug, but it will look exactly like "the
click was never recorded" during this walkthrough if you pick your own
made-up ref instead of a valid hex one.

### Read the stored hit back out of KV

```
npx wrangler kv key get --binding=CLICKS "click:abc123"
```

(swap `abc123` for whichever ref you actually used). On success this
prints the JSON array the Worker appended to, e.g.:

```
[{"path":"/case-studies/example.html","ts":"2026-08-23T12:00:00.000Z"}]
```

An empty result or a "key not found" error means the click was never
recorded -- first confirm the ref you used is valid hex (see above; an
invalid ref is silently dropped and is the most likely cause), then check
`wrangler tail` output for errors, confirm the KV `binding`/`id` in
`wrangler.toml` matches what you created in step 2, and confirm
`CLICK_BEACON_URL` in the deployed site matches the Worker's actual URL
exactly (protocol + host, no trailing path).

### List all recorded refs (sanity check after real traffic)

```
npx wrangler kv key list --binding=CLICKS
```

Lists every `click:<ref>` key currently stored -- confirms the pipeline is
live end to end, not just reachable.
