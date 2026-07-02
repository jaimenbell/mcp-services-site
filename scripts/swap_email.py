#!/usr/bin/env python3
"""One-shot placeholder swap for the mcp-services-site static site.

Replaces every occurrence of the ``[EMAIL]`` placeholder with a real contact
address across all tracked text files, and (optionally) repoints the primary
"Book a scoping call" buttons at a Calendly link instead of a ``mailto:``.

The site is plain static HTML with no build step, so there is no single
source-of-truth template to edit - this script is that single point instead.
It is count-verified: it refuses to report success unless the number of
replacements it made matches what it found, and it fails loudly (non-zero
exit) if the placeholder is missing entirely (already swapped, or the file
layout changed) so a bad run can never look silent-green.

Usage:
    python scripts/swap_email.py you@example.com
    python scripts/swap_email.py you@example.com --calendly https://calendly.com/you/scoping-call
    python scripts/swap_email.py you@example.com --dry-run

Exit codes: 0 = swap applied (or dry-run showed a clean plan), 1 = nothing to
do / verification mismatch / bad input.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Extensions we touch. The site is HTML + one README; no build artifacts.
TARGET_GLOBS = ("*.html", "*.md")
# Never touch these even if they matched a glob.
EXCLUDE_DIRS = {".git", "scripts", "node_modules", ".venv"}

EMAIL_PLACEHOLDER = "[EMAIL]"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# The primary CTA buttons this site labels "Book a scoping call" all share
# this exact mailto href shape once EMAIL is filled in. Calendly swap targets
# only this href - nav/footer "Contact" mailto links are left untouched on
# purpose, matching the README's documented manual behavior.
def scoping_call_href(email: str) -> str:
    return f'href="mailto:{email}?subject=MCP%20scoping%20call"'


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for pattern in TARGET_GLOBS:
        for path in REPO_ROOT.rglob(pattern):
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            files.append(path)
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Real contact address to fill in for [EMAIL]")
    parser.add_argument(
        "--calendly",
        metavar="URL",
        help="If given, also repoint the 5 primary 'Book a scoping call' "
             "buttons at this Calendly URL instead of mailto:",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing any files",
    )
    args = parser.parse_args()

    if not EMAIL_RE.match(args.email):
        print(f"error: '{args.email}' doesn't look like an email address", file=sys.stderr)
        return 1

    files = iter_target_files()
    if not files:
        print("error: no target files found (expected .html/.md under repo root)", file=sys.stderr)
        return 1

    total_email_replacements = 0
    total_calendly_replacements = 0
    touched_files: list[str] = []

    for path in files:
        text = path.read_text(encoding="utf-8")
        original = text

        email_hits = text.count(EMAIL_PLACEHOLDER)
        if email_hits:
            text = text.replace(EMAIL_PLACEHOLDER, args.email)

        calendly_hits = 0
        if args.calendly:
            old_href = scoping_call_href(args.email)
            new_href = f'href="{args.calendly}"'
            calendly_hits = text.count(old_href)
            if calendly_hits:
                text = text.replace(old_href, new_href)

        if text != original:
            rel = path.relative_to(REPO_ROOT).as_posix()
            touched_files.append(rel)
            print(f"{rel}: {email_hits} [EMAIL] -> address"
                  + (f", {calendly_hits} scoping-call mailto -> Calendly" if args.calendly else ""))
            total_email_replacements += email_hits
            total_calendly_replacements += calendly_hits
            if not args.dry_run:
                path.write_text(text, encoding="utf-8")

    if total_email_replacements == 0:
        print("error: found 0 [EMAIL] placeholders - already swapped, or repo layout changed. "
              "Refusing to report success on a no-op.", file=sys.stderr)
        return 1

    # Count-verify: re-scan (skip on dry-run since nothing was written).
    if not args.dry_run:
        remaining = sum(p.read_text(encoding="utf-8").count(EMAIL_PLACEHOLDER) for p in files)
        if remaining != 0:
            print(f"error: verification failed - {remaining} [EMAIL] placeholder(s) still present "
                  "after swap", file=sys.stderr)
            return 1

    mode = "DRY RUN - no files written" if args.dry_run else "APPLIED"
    print(f"\n[{mode}] {total_email_replacements} [EMAIL] occurrence(s) across {len(touched_files)} file(s).")
    if args.calendly:
        print(f"[{mode}] {total_calendly_replacements} scoping-call button(s) repointed to Calendly.")
        if total_calendly_replacements == 0:
            print("warning: --calendly was given but 0 scoping-call buttons matched - "
                  "check the email arg matches what's in the HTML.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
