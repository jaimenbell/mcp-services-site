/* ============================================================================
   DISCORD COMMUNITY CTA — single source of truth for the invite URL.

   TODO(operator): the Discord server does not exist yet. Once it's built and
   the pre-invite checklist is done (backfilled build-log, first fleet card,
   rules pinned), paste the real invite link below and republish the site.

   Every Discord CTA on the site — the hero-adjacent "join the build" band on
   the homepage, and the footer link on every article/case-study page — reads
   this ONE constant. Never ships a dead invite link.

   CHANGED 2026-09-09: the CTAs used to be hidden by an inline style="display:none"
   in the markup that ONLY this script could clear, so a visitor with JavaScript
   disabled never saw the band or the footer link at all -- a conversion defect,
   not just an a11y one. The markup now ships visible with the real href, and
   this script ENFORCES the hide in the other direction: if DISCORD_INVITE is
   emptied, it hides every CTA on load. That keeps the "never ships a dead
   invite link" guarantee for the JS path, and the no-JS path is covered by
   tests/test_discord_cta_parity.py, which fails the suite if the constant and
   the markup ever disagree.
   ============================================================================ */
var DISCORD_INVITE = "https://discord.gg/Xw3QNsUdYh"; // The Exit Strategy — unified AI builder community (never-expires)

(function () {
  var invite = (DISCORD_INVITE || "").trim();

  function sync(wrapId, linkId) {
    var wrap = document.getElementById(wrapId);
    var link = document.getElementById(linkId);
    if (!wrap || !link) return;
    if (invite) {
      link.href = invite;      // this constant stays the source of truth for the URL
      wrap.style.display = "";
    } else {
      wrap.style.display = "none"; // emptied invite -> hide, never ship a dead link
    }
  }

  sync("discord-cta", "discord-cta-link");
  sync("discord-footer-link-wrap", "discord-footer-link");
})();
