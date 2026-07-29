/* ============================================================================
   EXAMPLE Cloudflare Worker — click-beacon receiver for js/click-track.js.

   NOT DEPLOYED. This file is a reference only: nothing in this repo runs it,
   calls it, or depends on it existing. It is the concrete "cheapest thing
   that would work" for observing a click on a static GitHub Pages site with
   no server-side logs (see js/click-track.js header for the full context).

   PENDING OPERATOR SETUP to make this real:
     1. Sign up for Cloudflare's free plan (no card required for this volume;
        Workers free tier = 100k requests/day).
     2. Create a new Worker, paste this file's contents in as its script.
     3. Create a KV namespace (e.g. "CLICKS") and bind it to the Worker as
        `CLICKS` in the Worker's settings.
     4. Note the Worker's *.workers.dev URL (or map a route on your zone).
     5. Paste that URL into CLICK_BEACON_URL in js/click-track.js and
        republish the site.
   None of this is done by this lane -- account/service creation is outside
   what an unattended build step should do. This file exists so step 2 is a
   paste, not a from-scratch design exercise.

   What it does: accepts a POST {ref, path, ts} from click-track.js, appends
   it to KV under a per-ref list (so multiple hits on the same ref accumulate
   rather than overwrite), and returns 204. Rejects everything else. Records
   ONLY what click-track.js sends -- an opaque ref, a path, a timestamp. No
   name, no email, no IP is intentionally read or stored here.
   ============================================================================ */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405 });
    }

    let body;
    try {
      body = await request.json();
    } catch (e) {
      return new Response("bad json", { status: 400 });
    }

    const ref = String(body.ref || "").slice(0, 64);
    const path = String(body.path || "").slice(0, 256);
    const ts = String(body.ts || new Date().toISOString()).slice(0, 40);

    if (!/^[0-9a-f]{6,64}$/i.test(ref)) {
      // Not a plausible linktrack.make_ref() token -- ignore silently rather
      // than let arbitrary POSTs pollute KV.
      return new Response(null, { status: 204 });
    }

    const key = `click:${ref}`;
    const existingRaw = await env.CLICKS.get(key);
    const hits = existingRaw ? JSON.parse(existingRaw) : [];
    hits.push({ path, ts });
    await env.CLICKS.put(key, JSON.stringify(hits));

    return new Response(null, { status: 204 });
  },
};

/* To read hits back later (e.g. from `wrangler kv key get --binding=CLICKS
   click:<ref>`), resolve <ref> to a prospect via
   `python -m sales_reps.linktrack` / data/link_map.jsonl in the sales-reps
   repo -- this Worker never sees or stores which prospect a ref belongs to,
   only sales-reps' local, gitignored mapping does. */
