/* ============================================================================
   MEMBER PORTAL CTA — single source of truth for the go-live flip.

   TODO(operator): the Exit Strategy Portal's $9/mo MEMBER tier is built and
   proven in test mode (E2E verified 2026-07-22) but is NOT yet publicly
   purchasable — go-live is a separate ceremony. Until PORTAL_SIGNUP_URL is
   filled in below, the CTA reads "Get notified at launch" and mails the
   operator instead of claiming a live purchase flow.

   On go-live day: paste the real signup/checkout URL into PORTAL_SIGNUP_URL
   and republish. The button text and price-note flip automatically — no
   other HTML edit required. Never ship this filled in before the portal is
   actually open for signups.
   ============================================================================ */
var PORTAL_SIGNUP_URL = ""; // e.g. https://portal.jaimenbell.dev/signup -- set on go-live day

(function () {
  var link = document.getElementById("member-cta-link");
  if (!link) return;
  var note = document.getElementById("member-cta-note");
  var url = (PORTAL_SIGNUP_URL || "").trim();

  if (url) {
    link.href = url;
    link.textContent = "Join — $9/mo";
    if (note) {
      note.innerHTML = '<span class="lock">⬡</span> Cancel anytime · billed monthly · no trading advice, ever';
    }
  } else {
    link.href = "mailto:jaime@jaimenbell.dev?subject=Membership%20launch%20-%20notify%20me&body=Ping%20me%20when%20the%20%249%2Fmo%20membership%20opens.";
    link.textContent = "Get notified at launch";
    // note left as authored in HTML: honest "test mode, not yet purchasable" state
  }
})();
