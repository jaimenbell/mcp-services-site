/* ============================================================================
   DISCORD COMMUNITY CTA — single source of truth for the invite URL.

   TODO(operator): the Discord server does not exist yet. Once it's built and
   the pre-invite checklist is done (backfilled build-log, first fleet card,
   rules pinned), paste the real invite link below and republish the site.

   Every Discord CTA on the site — the hero-adjacent "join the build" band on
   the homepage, and the footer link on every article/case-study page — reads
   this ONE constant and stays hidden until it's filled in. Never ships a dead
   invite link.
   ============================================================================ */
var DISCORD_INVITE = "https://discord.gg/wBAjtpBHn"; // The Exit Strategy — unified AI builder community

(function () {
  var invite = (DISCORD_INVITE || "").trim();
  if (!invite) return; // nothing filled in yet — leave every CTA hidden

  var band = document.getElementById("discord-cta");
  var bandLink = document.getElementById("discord-cta-link");
  if (band && bandLink) {
    bandLink.href = invite;
    band.style.display = "";
  }

  var footerWrap = document.getElementById("discord-footer-link-wrap");
  var footerLink = document.getElementById("discord-footer-link");
  if (footerWrap && footerLink) {
    footerLink.href = invite;
    footerWrap.style.display = "";
  }
})();
