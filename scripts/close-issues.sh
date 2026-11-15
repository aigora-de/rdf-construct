#!/usr/bin/env bash
#
# close-issues.sh — close the issues a merged release-branch PR says it closes.
#
# Copyright (c) 2026 Dave Dyke / Agilit Ltd. MIT licence.
#
# main holds the last release, and work for the next one merges into
# release/vX.Y.Z. GitHub acts on `Closes #N` only when a PR merges into the
# default branch, which is main, so a PR merged into a release branch leaves
# its issues open, and the milestone's open count stops meaning anything. Run
# this after each such merge.
#
# The issue numbers come from the PR's title and body, because that is the
# squash commit's message: the same closing keywords GitHub honours (close,
# closes, closed, fix, fixes, fixed, resolve, resolves, resolved), for issues in
# this repository only. Each issue gets a comment saying where the fix landed
# and which release carries it, and is closed as completed. An issue that is
# already closed is left alone, so running it twice is harmless.
#
# Usage:
#   scripts/close-issues.sh -n | --check <PR>   # lists what it would close; changes nothing
#   scripts/close-issues.sh <PR>                # comments on and closes each issue
#   scripts/close-issues.sh -h | --help

set -uo pipefail

usage() {
  cat <<'USAGE'
close-issues.sh — close the issues a merged release-branch PR says it closes.

GitHub honours `Closes #N` only for a PR merged into the default branch (main).
Work merges into release/vX.Y.Z, so its issues have to be closed by hand.

  scripts/close-issues.sh -n | --check <PR>   lists what it would close; changes nothing
  scripts/close-issues.sh <PR>                comments on and closes each issue
  scripts/close-issues.sh -h | --help

Refuses a PR that is not merged, or not merged into a release/v* branch.
USAGE
}

MODE=run
case "${1-}" in
  -n|--check)  MODE=check; shift ;;
  -h|--help)   usage; exit 0 ;;
esac

PR="${1-}"
if [[ ! "$PR" =~ ^[0-9]+$ ]]; then
  echo "give a PR number (try --help)" >&2
  exit 2
fi

for tool in gh jq; do
  command -v "$tool" >/dev/null || { echo "$tool is required and was not found" >&2; exit 2; }
done

FAILED=()

say()  { printf '\n\033[1m──▶ %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32m✓ %s\033[0m\n' "$1"; }
bad()  { printf '   \033[31m✗ %s\033[0m\n' "$1"; FAILED+=("$1"); }
note() { printf '     \033[2m%s\033[0m\n' "$1"; }

say "PR #$PR"
pr="$(gh api "repos/:owner/:repo/pulls/$PR" 2>/dev/null)" || {
  echo "could not read PR #$PR" >&2
  exit 2
}
merged="$(jq -r '.merged' <<<"$pr")"
base="$(jq -r '.base.ref' <<<"$pr")"
text="$(jq -r '.title + "\n" + (.body // "")' <<<"$pr")"

if [[ "$merged" != true ]]; then
  bad "not merged — nothing closes until it is"
elif [[ "$base" != release/v* ]]; then
  bad "merged into '$base', not a release/v* branch"
  [[ "$base" == main ]] && note "GitHub closes the issues of a PR merged into main itself"
else
  ok "merged into $base"
fi
if (( ${#FAILED[@]} )); then exit 1; fi

release="${base#release/}"

# Same-repository references only: `owner/repo#N` is somebody else's issue.
issues="$(grep -oiE '(^|[^[:alnum:]_/])(close[sd]?|fix(e[sd])?|resolve[sd]?):?[[:space:]]+#[0-9]+' <<<"$text" \
  | grep -oE '[0-9]+$' | sort -un)"
if [[ -z "$issues" ]]; then
  ok "it closes no issues"
  exit 0
fi

for n in $issues; do
  say "issue #$n"
  issue="$(gh api "repos/:owner/:repo/issues/$n" 2>/dev/null)" || { bad "#$n: could not read it"; continue; }
  if [[ "$(jq -r 'has("pull_request")' <<<"$issue")" == true ]]; then
    ok "#$n is a pull request — left alone"
    continue
  fi
  note "$(jq -r '.title' <<<"$issue")"
  if [[ "$(jq -r '.state' <<<"$issue")" == closed ]]; then
    ok "already closed"
    continue
  fi
  if [[ "$MODE" == check ]]; then
    ok "would close, as fixed by #$PR in $release"
    continue
  fi
  # Close first: a rerun skips a closed issue, so a failed comment is never
  # posted twice. A missing comment is the cheaper thing to leave behind.
  if ! gh api -X PATCH "repos/:owner/:repo/issues/$n" \
      -f state=closed -f state_reason=completed >/dev/null 2>&1; then
    bad "#$n: could not close it"
  elif gh api "repos/:owner/:repo/issues/$n/comments" \
      -f body="Fixed by #$PR, merged into \`$base\`. It ships in $release." >/dev/null 2>&1; then
    ok "closed, as fixed by #$PR in $release"
  else
    bad "#$n: closed, but the comment could not be posted"
  fi
done

if (( ${#FAILED[@]} )); then
  printf '\n  \033[31mFAILED: %s\033[0m\n' "${FAILED[*]}"
  exit 1
fi
