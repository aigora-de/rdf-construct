#!/usr/bin/env bash
#
# retarget-prs.sh — move PRs opened against main onto the release branch they belong to.
#
# Copyright (c) 2026 Dave Dyke / Agilit Ltd. MIT licence.
#
# main holds the last release and stays the default branch, so a contributor who
# has not read CONTRIBUTING.md opens their PR against it. Work for the next
# release lands on release/vX.Y.Z instead. This finds each open PR based on main
# and retargets it:
#
#   - to the release branch of the milestone of the issue it closes, when that
#     branch exists on origin. A patch release such as v0.6.1 is a maintainer's
#     decision, made by opening its milestone and cutting release/v0.6.1 from
#     main, and this is how its fixes reach it;
#   - otherwise to the newest release branch. That covers an issue with no
#     milestone, and one whose release has no branch yet (a v0.7.1 issue before
#     v0.7.0 ships lands in v0.7.0).
#
# The issues come from the PR's title and body, with the closing keywords GitHub
# honours, exactly as close-issues.sh reads them. If they name milestones whose
# branches differ, the PR is left for a person to decide. A PR already on a
# release branch is left alone.
#
# The PR is retargeted first and commented on second, so a rerun after a failed
# comment finds it no longer on main and never posts twice.
#
# Usage:
#   scripts/retarget-prs.sh -n | --check [PR...]   # shows each decision; changes nothing
#   scripts/retarget-prs.sh [PR...]                # retargets, and comments on each
#   scripts/retarget-prs.sh -h | --help
#
# With no PR numbers, every open PR based on main is considered.

set -uo pipefail

usage() {
  cat <<'USAGE'
retarget-prs.sh — move PRs opened against main onto the release branch they belong to.

main holds the last release; work lands on release/vX.Y.Z. Each open PR based on
main goes to the release branch of its issue's milestone, if that branch exists,
or else to the newest release branch.

  scripts/retarget-prs.sh -n | --check [PR...]   shows each decision; changes nothing
  scripts/retarget-prs.sh [PR...]                retargets, and comments on each
  scripts/retarget-prs.sh -h | --help

With no PR numbers, every open PR based on main is considered. A PR whose issues
point at different release branches is left for a person to decide.
USAGE
}

MODE=run
case "${1-}" in
  -n|--check)  MODE=check; shift ;;
  -h|--help)   usage; exit 0 ;;
esac

for pr in "$@"; do
  [[ "$pr" =~ ^[0-9]+$ ]] || { echo "not a PR number: $pr (try --help)" >&2; exit 2; }
done

for tool in gh jq; do
  command -v "$tool" >/dev/null || { echo "$tool is required and was not found" >&2; exit 2; }
done

FAILED=()

say()  { printf '\n\033[1m──▶ %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32m✓ %s\033[0m\n' "$1"; }
bad()  { printf '   \033[31m✗ %s\033[0m\n' "$1"; FAILED+=("$1"); }
note() { printf '     \033[2m%s\033[0m\n' "$1"; }

branches="$(gh api "repos/:owner/:repo/branches" --paginate --jq '.[].name' 2>/dev/null \
  | grep -E '^release/v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V)"
if [[ -z "$branches" ]]; then
  echo "no release/vX.Y.Z branch on origin — nothing to retarget to" >&2
  exit 2
fi
newest="$(tail -1 <<<"$branches")"

if (( $# )); then
  prs="$*"
else
  prs="$(gh api "repos/:owner/:repo/pulls?state=open&base=main" --paginate --jq '.[].number' 2>/dev/null)"
  if [[ -z "$prs" ]]; then
    say "open PRs based on main"
    ok "none"
    exit 0
  fi
fi

for n in $prs; do
  say "PR #$n"
  pr="$(gh api "repos/:owner/:repo/pulls/$n" 2>/dev/null)" || { bad "#$n: could not read it"; continue; }
  note "$(jq -r '.title' <<<"$pr")"
  if [[ "$(jq -r '.state' <<<"$pr")" != open ]]; then
    ok "not open — left alone"
    continue
  fi
  base="$(jq -r '.base.ref' <<<"$pr")"
  if [[ "$base" != main ]]; then
    ok "based on $base — left alone"
    continue
  fi

  # Same-repository references only, as in close-issues.sh.
  issues="$(jq -r '.title + "\n" + (.body // "")' <<<"$pr" \
    | grep -oiE '(^|[^[:alnum:]_/])(close[sd]?|fix(e[sd])?|resolve[sd]?):?[[:space:]]+#[0-9]+' \
    | grep -oE '[0-9]+$' | sort -un)"

  # Each issue's milestone names a release; its branch counts only if it exists.
  wanted=()
  for i in $issues; do
    milestone="$(gh api "repos/:owner/:repo/issues/$i" --jq '.milestone.title // ""' 2>/dev/null)"
    version="$(grep -oE '^v[0-9]+\.[0-9]+\.[0-9]+' <<<"$milestone")"
    if [[ -n "$version" ]] && grep -qx "release/$version" <<<"$branches"; then
      note "#$i is in $version, which has its branch"
      wanted+=("release/$version")
    elif [[ -n "$version" ]]; then
      note "#$i is in $version, which has no branch yet"
    else
      note "#$i has no release milestone"
    fi
  done
  [[ -z "$issues" ]] && note "it names no issue"

  distinct="$(printf '%s\n' "${wanted[@]+"${wanted[@]}"}" | sed '/^$/d' | sort -u)"
  if [[ "$(sed '/^$/d' <<<"$distinct" | wc -l | tr -d ' ')" -gt 1 ]]; then
    bad "#$n: its issues point at different branches (${distinct//$'\n'/ }) — decide by hand"
    continue
  fi
  target="${distinct:-$newest}"
  reason="newest release branch"
  [[ -n "$distinct" ]] && reason="its issue's milestone"

  if [[ "$MODE" == check ]]; then
    ok "would retarget to $target ($reason)"
    continue
  fi
  now="$(gh api -X PATCH "repos/:owner/:repo/pulls/$n" -f base="$target" --jq '.base.ref' 2>/dev/null)"
  if [[ "$now" != "$target" ]]; then
    bad "#$n: could not retarget it to $target"
    continue
  fi
  if gh api "repos/:owner/:repo/issues/$n/comments" -f body="Thanks for this. \`main\` holds the last release, and work for the next one lands on a release branch, so I've retargeted this PR to \`$target\`. Your commits are unchanged and there's nothing you need to do. \`CONTRIBUTING.md\` has the details." >/dev/null 2>&1; then
    ok "retargeted to $target ($reason); $(gh api "repos/:owner/:repo/pulls/$n" --jq '.commits') commit(s) in its diff"
  else
    bad "#$n: retargeted to $target, but the comment could not be posted"
  fi
done

if (( ${#FAILED[@]} )); then
  printf '\n  \033[31mFAILED: %s\033[0m\n' "${FAILED[*]}"
  exit 1
fi
