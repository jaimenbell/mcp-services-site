/* ============================================================================
   TRACKED-LINK CLICK CAPTURE — F4 half that lives on this site.

   ⚠ STATUS (corrected 2026-08-26): THIS FILE IS INERT. It reads a `?ref=` and
   stashes it; it sends nothing anywhere, because CLICK_BEACON_URL is empty.
   Do not read its presence in a page as attribution coverage.

   ⚠ The 2026-07-29 claim that this site has "NO analytics of any kind wired"
   is now STALE and was corrected here rather than left to mislead: GoatCounter
   WAS wired 2026-08-20 (see index.html's data-goatcounter tag and
   docs/INSTRUMENTATION-SETUP.md). GoatCounter gives PAGEVIEWS. It does NOT
   give per-prospect `?ref=` attribution — that is what this file would do if
   it had an endpoint, and the two are not substitutes.

   Still true: this is static GitHub Pages with no server-side logs, and
   GitHub's repo Traffic API only covers github.com views of the REPO page,
   not this custom-domain Pages site, so it observes nothing here either.
   A `?ref=` tag on a URL is therefore inert on arrival — nothing records the
   attribution — until CLICK_BEACON_URL below points at a real endpoint.

   Cheapest real fix once you're ready to wire it: a free Cloudflare Worker
   (Workers free tier, no card required for this volume) that accepts a POST
   {ref, path, ts}, appends it to Workers KV or just logs it, and returns 204.
   A ready-to-deploy example is in scripts/click-beacon-worker.example.js in
   this repo — paste its contents into a new Worker, note the worker's URL,
   and paste THAT URL into CLICK_BEACON_URL below. Until that happens this
   file only reads and stashes the ref; it sends nothing anywhere.

   Every prospect link built by sales-reps' drafter.build_site_link() carries
   a `?ref=<opaque token>` — never a name/email, see sales_reps/linktrack.py.
   This snippet is the read-and-record side; the send side never exists in
   this repo (same "generate but don't act" posture as discord-cta.js /
   member-cta.js above it).
   ============================================================================ */
var CLICK_BEACON_URL = ""; // e.g. https://click-beacon.<you>.workers.dev -- set once deployed

(function () {
  var params = new URLSearchParams(window.location.search);
  var ref = (params.get("ref") || "").trim();
  if (!ref) return; // no tracked visit on this load -- nothing to do

  // Survive same-tab navigation within the site (e.g. landing -> case study)
  // so a beacon endpoint added later can still attribute the whole session,
  // not just the first page hit.
  try {
    window.sessionStorage.setItem("jnb_ref", ref);
  } catch (e) {
    /* sessionStorage unavailable (private mode, etc.) -- fine, best-effort only */
  }

  var endpoint = (CLICK_BEACON_URL || "").trim();
  if (!endpoint) {
    // Be LOUD, not silent. A tracked link just arrived and we are dropping it
    // on the floor. Silence here is what let this read as "attribution is
    // wired" for weeks -- an instrument that looks live and sends nowhere is
    // worse than no instrument, because it stops anyone from looking.
    if (window.console && console.warn) {
      console.warn(
        "[click-track] INERT: received ?ref=" + ref + " but CLICK_BEACON_URL " +
        "is empty, so this visit was NOT attributed and nothing was sent. " +
        "Deploy scripts/click-beacon-worker.example.js and set CLICK_BEACON_URL. " +
        "GoatCounter pageviews do NOT cover this -- they carry no ?ref."
      );
    }
    return;
  }

  var payload = JSON.stringify({
    ref: ref,
    path: window.location.pathname,
    ts: new Date().toISOString(),
  });

  if (navigator.sendBeacon) {
    var blob = new Blob([payload], { type: "application/json" });
    navigator.sendBeacon(endpoint, blob);
  } else {
    fetch(endpoint, { method: "POST", body: payload, keepalive: true,
                       headers: { "Content-Type": "application/json" } })
      .catch(function () { /* best-effort; never block the page on this */ });
  }
})();
