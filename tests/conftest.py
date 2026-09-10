"""Shared test-only helpers (finding 9, review 2).

_git_clean_env() lived only in tests/test_check_proof_numbers.py (added for
finding 10, first review) -- tests/test_check_beacon_coverage.py's own
git-spawning helpers (_hook_env(), _build_temp_hook_repo()) never adopted
it, so that file's first-review fix covered only one of the two files that
needed it. A conftest.py helper is importable by every test module in this
directory without a fragile cross-test-file import, so both files now share
exactly one implementation.
"""

import os


def _git_clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A subprocess env with every GIT_* var stripped. Git exports
    GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE (and friends) to its own hook's
    subprocess environment -- if a test module's git-spawning helpers ever
    run FROM inside a git hook (e.g. this very repo's own pre-commit, or a
    live_verify_manifest() invocation from ANOTHER repo's hook that targets
    this repo's test suite as a source_cmd) and inherit those vars
    unscrubbed, a `git init`/`git worktree add`/`git commit` in a tmp
    fixture repo would silently target the OUTER repo's git internals
    instead of the tmp repo it's meant to operate on -- see
    check_proof_numbers.py's own `clean_env` comment in
    live_verify_manifest() for the production-code sibling of this exact
    fix. `extra` merges additional/overriding entries on top."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if extra:
        env.update(extra)
    return env
