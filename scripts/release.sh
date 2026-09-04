#!/usr/bin/env bash
#
# release.sh — the release runner for rdf-construct.
#
# Copyright (c) 2026 Dave Dyke / Agilit Ltd. MIT licence.
#
# Companion to ci-local.sh, which gates a PR. This gates a release (#98).
#
# It exists because the manual sequence was skipped, repeatedly and silently:
# four published versions (0.4.1, 0.4.4, 0.4.5, 0.4.6) were never tagged at all,
# twelve of thirteen never got a GitHub release, and README sat four versions
# stale. None of that was caught, because nothing was checking.
#
# The design rule is REFUSE, DON'T ASSIST. Every check below fails the run and
# tells you what to fix; the script never edits a file to make itself pass. The
# one irreversible step — uploading to PyPI, which can never be undone for a
# given version — it deliberately does NOT perform. It prepares and verifies
# everything, then hands you one command.
#
# Usage:
#   scripts/release.sh -n | --check   # checks only; changes nothing, anywhere
#   scripts/release.sh                # check, build, verify, tag, push, dry-run
#   scripts/release.sh --post         # after publishing: GitHub release, milestone
#   scripts/release.sh -h | --help
#
# The build comes before the tag deliberately. A tag that has been pushed cannot
# be quietly retracted once anyone has fetched it, so nothing is published to
# origin until the artefact exists and has been proven to work.
#
# Override the Python runner with CI_LOCAL_PYRUN (default "poetry run"), as for
# ci-local.sh.

set -uo pipefail

usage() {
  # A heredoc, not a line-range slice of this file's own comments. ci-local.sh
  # does the latter and it silently drifted (#93); no point repeating that here.
  cat <<'USAGE'
release.sh — the release runner for rdf-construct.

Companion to ci-local.sh: that one gates a PR, this one gates a release.

  scripts/release.sh -n | --check   checks only; changes nothing, anywhere
  scripts/release.sh                check, build, verify, tag, push, dry-run
  scripts/release.sh --post         after publishing: GitHub release, milestone
  scripts/release.sh -h | --help

The default run stops before uploading to PyPI and prints the command for you
to run. A published version can never be replaced, so that step stays human.

The build happens before the tag: a pushed tag cannot be quietly retracted once
anyone has fetched it, so nothing reaches origin until the artefact exists and
has been proven to work.

Checks performed:

  git        on main, tracked tree clean, in sync with origin
  gate       scripts/ci-local.sh passes
  versions   pyproject.toml = __init__.py = CHANGELOG = README.md = CLAUDE.md
  changelog  top entry is dated, matches the version, [Unreleased] is empty,
             the footer carries this version's compare link, and the Version
             History Summary table's top row is this version, dated to match
  tag        does not already exist, locally or on origin

Then: a clean dist/; a build; the wheel installed into a throwaway venv and
asked its own --version; an annotated tag on the exact commit that was built,
pushed; and poetry publish --dry-run.
USAGE
}

MODE=run
case "${1-}" in
  -n|--check)  MODE=check ;;
  --post)      MODE=post ;;
  -h|--help)   usage; exit 0 ;;
  "")          ;;
  *)           echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

cd "$(git rev-parse --show-toplevel)" || { echo "not in a git repo" >&2; exit 2; }

PYRUN="${CI_LOCAL_PYRUN-poetry run}"
FAILED=()
# Set by do_build, read by do_tag. Initialised here so `set -u` gives a clear
# failure rather than an unbound-variable crash if the order is ever changed.
RELEASE_SHA=""

say()  { printf '\n\033[1m──▶ %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32m✓ %s\033[0m\n' "$1"; }
bad()  { printf '   \033[31m✗ %s\033[0m\n' "$1"; FAILED+=("$1"); }
note() { printf '     \033[2m%s\033[0m\n' "$1"; }

# --- the version under release ------------------------------------------------

VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
if [[ -z "$VERSION" ]]; then
  echo "could not read a version from pyproject.toml" >&2
  exit 2
fi
TAG="v$VERSION"

printf '\033[1mrdf-construct release %s\033[0m\n' "$TAG"
[[ "$MODE" == check ]] && printf '\033[2mcheck only — nothing will be changed\033[0m\n'

# --- checks -------------------------------------------------------------------

check_git() {
  say "git state"
  local branch; branch="$(git rev-parse --abbrev-ref HEAD)"
  [[ "$branch" == main ]] && ok "on main" || bad "on '$branch', not main"

  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    bad "tracked files are modified — commit or revert first"
  else
    ok "tracked tree clean"
  fi

  git fetch --quiet origin 2>/dev/null
  local ahead behind
  ahead="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
  behind="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)"
  if [[ "$ahead" == 0 && "$behind" == 0 ]]; then
    ok "in sync with origin/main"
  else
    bad "out of sync with origin/main ($ahead ahead, $behind behind)"
  fi
}

check_gate() {
  say "pre-release gate (ci-local.sh)"
  if ./scripts/ci-local.sh >/tmp/release-gate.$$ 2>&1; then
    ok "gate green"
  else
    bad "ci-local.sh gate failed"
    note "full output: /tmp/release-gate.$$"
    tail -5 "/tmp/release-gate.$$" | sed 's/^/     /'
    return
  fi
  rm -f "/tmp/release-gate.$$"
}

# Every place the version is written by hand. ci-local.sh gates the first two;
# README and CLAUDE.md are the ones that actually drifted, so they are here.
check_versions() {
  say "version strings agree ($VERSION)"

  local init; init="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/rdf_construct/__init__.py | head -1)"
  [[ "$init" == "$VERSION" ]] && ok "src/rdf_construct/__init__.py" \
    || bad "__init__.py says '$init', pyproject.toml says '$VERSION'"

  local readme_bad=0
  while IFS= read -r found; do
    [[ "$found" == "$VERSION" ]] || readme_bad=1
  done < <(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' README.md | sed 's/^v//')
  if [[ "$readme_bad" == 0 ]]; then
    ok "README.md"
  else
    bad "README.md names a version other than $VERSION"
    note "$(grep -nE 'v[0-9]+\.[0-9]+\.[0-9]+' README.md | head -3 | tr '\n' ' ')"
  fi

  if grep -q "v$VERSION" CLAUDE.md; then
    ok "CLAUDE.md"
  else
    bad "CLAUDE.md does not name v$VERSION"
    note "it also states a command and subpackage count — check those while you are there"
  fi
}

check_changelog() {
  say "CHANGELOG"

  local top entry_date=""
  top="$(grep -m1 -E '^## \[[0-9]' CHANGELOG.md)"
  if [[ "$top" =~ ^\#\#\ \[$VERSION\]\ -\ ([0-9]{4}-[0-9]{2}-[0-9]{2})$ ]]; then
    entry_date="${BASH_REMATCH[1]}"
    ok "top entry is [$VERSION], dated $entry_date"
  else
    bad "top dated entry is not '## [$VERSION] - YYYY-MM-DD'"
    note "found: $top"
  fi

  # Content still sitting under [Unreleased] should have been part of this
  # release, or should not be claimed by it.
  local unreleased
  unreleased="$(awk '/^## \[Unreleased\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md | grep -cE '^\s*-' || true)"
  if [[ "$unreleased" == 0 ]]; then
    ok "[Unreleased] is empty"
  else
    local s; [[ "$unreleased" == 1 ]] && s="entry" || s="entries"
    bad "[Unreleased] still has $unreleased $s — fold them in or move them out"
  fi

  grep -q "^\[$VERSION\]: .*compare/.*\.\.\.v$VERSION$" CHANGELOG.md \
    && ok "footer has the compare link for $VERSION" \
    || bad "footer has no 'compare/…...v$VERSION' link for this version"

  grep -q "^\[Unreleased\]: .*compare/v$VERSION\.\.\.HEAD$" CHANGELOG.md \
    && ok "[Unreleased] link is based on v$VERSION" \
    || bad "[Unreleased] link does not read 'compare/v$VERSION...HEAD'"

  # The Version History Summary table is maintained by hand, and it drifted a
  # whole release before anyone noticed: the 0.5.0 row was never added, so the
  # table sat at 0.4.7 throughout the v0.6.0 cycle (#124).
  #
  # Only the TOP row is checked. The table has never been complete — 0.2.1 has a
  # section heading and a compare link but no row, from 2025-12-03 — so asserting
  # completeness would fail on history nobody is releasing, and a check that fails
  # for reasons outside the release is one people learn to skip.
  local row
  row="$(grep -m1 -E '^\| \[[0-9]+\.[0-9]+\.[0-9]+\] \|' CHANGELOG.md)"
  if [[ -z "$row" ]]; then
    bad "no version rows found in the Version History Summary table"
  elif [[ ! "$row" =~ ^\|\ \[$VERSION\]\ \| ]]; then
    bad "Version History Summary table has no row for $VERSION"
    note "its top row is: $row"
  elif [[ "$row" =~ ^\|\ \[$VERSION\]\ \|\ ([0-9]{4}-[0-9]{2}-[0-9]{2})\ \| ]] \
       && [[ -n "$entry_date" ]] && [[ "${BASH_REMATCH[1]}" != "$entry_date" ]]; then
    bad "summary table dates $VERSION ${BASH_REMATCH[1]}, the entry says $entry_date"
  else
    ok "summary table's top row is $VERSION"
  fi
}

check_tag() {
  say "tag $TAG is free"
  if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    bad "$TAG already exists locally"
  else
    ok "no local tag"
  fi
  if [[ -n "$(git ls-remote --tags origin "$TAG" 2>/dev/null)" ]]; then
    bad "$TAG already exists on origin"
  else
    ok "no remote tag"
  fi
}

# --- actions ------------------------------------------------------------------

# Tags the commit that was actually built, captured before the build, rather
# than whatever HEAD happens to be by now. Belt and braces — the checks refuse a
# dirty tree, so these are the same commit — but it makes the tag a statement
# about the artefact rather than about the clock.
do_tag() {
  say "tagging $TAG"
  if [[ "$(git rev-parse HEAD)" != "$RELEASE_SHA" ]]; then
    bad "HEAD moved during the run — refusing to tag"
    note "built ${RELEASE_SHA:0:8}, HEAD is now $(git rev-parse --short HEAD)"
    return
  fi
  git tag -a "$TAG" "$RELEASE_SHA" -m "Release $TAG" && ok "annotated tag on ${RELEASE_SHA:0:8}"
  git push origin "$TAG" >/dev/null 2>&1 && ok "pushed to origin" || bad "could not push $TAG"
}

do_build() {
  RELEASE_SHA="$(git rev-parse HEAD)"
  say "building into a clean dist/ (from ${RELEASE_SHA:0:8})"
  # Poetry only uploads artefacts matching the current version, so an old 0.4.x
  # in dist/ is harmless. A STALE 0.5.0 is not: it would publish an earlier tree
  # under the right filename. Clearing the directory makes that impossible.
  rm -rf dist/
  if $PYRUN poetry build >/tmp/release-build.$$ 2>&1 || poetry build >/tmp/release-build.$$ 2>&1; then
    ok "built $(ls dist/ | tr '\n' ' ')"
    rm -f "/tmp/release-build.$$"
  else
    bad "poetry build failed"
    tail -5 "/tmp/release-build.$$" | sed 's/^/     /'
  fi
}

# Install the artefact somewhere clean and ask it what it is. A non-editable
# install is exactly where a version read from package metadata would go wrong,
# which is how #66 hid for as long as it did.
do_verify() {
  say "verifying the built wheel"
  local wheel venv reported
  wheel="$(ls dist/*.whl 2>/dev/null | head -1)"
  if [[ -z "$wheel" ]]; then bad "no wheel in dist/"; return; fi

  venv="$(mktemp -d)"
  python3 -m venv "$venv" >/dev/null 2>&1
  if ! "$venv/bin/pip" install --quiet "$wheel" >/dev/null 2>&1; then
    bad "the wheel does not install"
    rm -rf "$venv"; return
  fi
  reported="$("$venv/bin/rdf-construct" --version 2>&1)"
  rm -rf "$venv"

  if [[ "$reported" == "rdf-construct, version $VERSION" ]]; then
    ok "installs clean and reports: $reported"
  else
    bad "installed wheel reports '$reported', expected 'rdf-construct, version $VERSION'"
  fi
}

do_dry_run() {
  say "publish dry run"
  poetry publish --dry-run 2>&1 | sed 's/^/     /'
}

# --- after you have published --------------------------------------------------

do_post() {
  say "GitHub release for $TAG"
  if gh release view "$TAG" >/dev/null 2>&1; then
    ok "release already exists"
  else
    local notes; notes="$(mktemp)"
    {
      echo "PyPI: https://pypi.org/project/rdf-construct/$VERSION/"
      echo
      echo '```'
      echo "pip install rdf-construct==$VERSION"
      echo '```'
      echo
      echo "---"
      echo
      awk -v v="$VERSION" '$0 ~ "^## \\["v"\\]"{f=1;next} /^## \[/{f=0} f' CHANGELOG.md
    } > "$notes"
    if gh release create "$TAG" --title "$TAG" --notes-file "$notes" --verify-tag >/dev/null 2>&1; then
      ok "created, notes taken from the CHANGELOG entry"
    else
      bad "gh release create failed"
    fi
    rm -f "$notes"
  fi

  say "milestone"
  local num open
  num="$(gh api repos/:owner/:repo/milestones --jq ".[] | select(.title | startswith(\"$TAG\")) | .number" 2>/dev/null | head -1)"
  if [[ -z "$num" ]]; then
    ok "no milestone named $TAG — nothing to close"
  else
    open="$(gh api "repos/:owner/:repo/milestones/$num" --jq .open_issues 2>/dev/null)"
    if [[ "$open" != 0 ]]; then
      bad "milestone $TAG still has $open open issues — move or close them first"
    elif gh api "repos/:owner/:repo/milestones/$num" -X PATCH -f state=closed >/dev/null 2>&1; then
      ok "milestone $TAG closed"
    else
      bad "could not close milestone $TAG"
    fi
  fi
}

# --- run ----------------------------------------------------------------------

check_git
check_gate
check_versions
check_changelog
[[ "$MODE" == post ]] || check_tag

summary() {
  printf '\n\033[1m── summary ─────────────────────────────\033[0m\n'
  if (( ${#FAILED[@]} )); then
    printf '  \033[31mFAILED: %s\033[0m\n' "${FAILED[*]}"
    printf '  nothing was published.\n'
    exit 1
  fi
}

if (( ${#FAILED[@]} )); then summary; fi

case "$MODE" in
  check)
    printf '\n\033[32m  all checks pass — %s is ready to release\033[0m\n' "$TAG"
    printf '  run \033[1mscripts/release.sh\033[0m to tag, build and verify.\n'
    ;;
  run)
    # Build and prove the artefact before anything reaches origin. A failed
    # build here leaves no public trace; the other order leaves a pushed tag to
    # retract, which is the recovery this script exists to spare you.
    do_build
    do_verify
    summary
    do_tag
    summary
    do_dry_run
    printf '\n\033[1m── ready ───────────────────────────────\033[0m\n'
    printf '  %s is tagged, pushed, built and verified.\n' "$TAG"
    printf '\n  The upload is yours — it cannot be undone, and there are no\n'
    printf '  credentials here. Run:\n\n'
    printf '      \033[1mpoetry publish\033[0m\n'
    printf '\n  Do NOT rebuild first; dist/ holds the verified artefacts.\n'
    printf '  Afterwards: \033[1mscripts/release.sh --post\033[0m\n'
    ;;
  post)
    do_post
    summary
    printf '\n\033[32m  %s is fully released.\033[0m\n' "$TAG"
    ;;
esac
