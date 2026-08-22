#!/usr/bin/env bash
#
# The block between the help:start and help:end markers below is what `--help`
# prints. It used to be a hard-coded line range, which drifted the moment anyone
# added a comment and silently emitted `set -uo pipefail` as help text (#93).
# Add or remove lines inside the markers freely; they move with the content.
#
# help:start
# ci-local.sh — the pre-PR check runner for rdf-construct.
#
# Copyright (c) 2026 Dave Dyke / Agilit Ltd. MIT licence.
#
# There is no hosted CI: .github/workflows/ contains only .gitkeep, so nothing runs on
# push, on a PR, or on a tag, and `gh pr checks` reports nothing. This script is the
# gate. Run it before opening or merging a PR (#74).
#
# GATE vs ADVISORY
#
#   GATE     — the test suite, black, the version-consistency check and the
#              instruction/memory size guard. A gate step's failure IS this script's
#              exit code.
#   ADVISORY — ruff and mypy. They run and report but do NOT fail the script, because
#              each carries substantial pre-existing debt measured across the whole
#              repository (see the tracking issues below). Gating on them today would
#              mean the script failed on every run from day one, and a check that
#              always fails is a check nobody reads.
#
# Keep the files YOUR change touches clean; you are not expected to fix the rest.
# When a debt lands at zero, flip its step from `advisory` to `gate` below — a
# one-word change — and restore its pre-commit hook.
#
#   ruff debt — #78   mypy --strict debt — #79
#
# black was the first to clear: #77 reformatted the repository, so it is a gate here
# and a pre-commit hook again.
#
# Runs every selected check even if an earlier one fails, then prints a summary and
# exits non-zero iff a GATE step failed. Override the Python runner with CI_LOCAL_PYRUN
# (default "poetry run"; set to "" inside an already-active venv).
#
# Usage:
#   scripts/ci-local.sh              # gates (pytest + black + memory guard) + advisory (ruff, mypy)
#   scripts/ci-local.sh --tests-only # the pytest gate alone (fast)
#   scripts/ci-local.sh --lint-only  # the non-pytest checks (black, ruff, mypy, memory guard)
#   scripts/ci-local.sh -h|--help
# help:end

set -uo pipefail

# Print the comment block between the help markers, minus the markers and the
# leading "# ". Bounded by content rather than by line number, so adding a
# comment above cannot silently push shell code into the help text (#93).
show_help() {
  awk '/^# help:start$/{f=1;next} /^# help:end$/{f=0} f' "$0" | sed 's/^# \{0,1\}//'
}

cd "$(git rev-parse --show-toplevel)" || { echo "not in a git repo" >&2; exit 2; }

PYRUN="${CI_LOCAL_PYRUN-poetry run}"
RUN_TESTS=1
RUN_OTHER=1
case "${1-}" in
  --tests-only) RUN_OTHER=0 ;;
  --lint-only)  RUN_TESTS=0 ;;
  -h|--help)    show_help; exit 0 ;;
  "")           ;;
  *)            echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

# Preflight: fail once, clearly, if the Python runner is missing — rather than five
# times with "command not found" as each step trips over it in turn.
runner="${PYRUN%% *}"
if [[ -n "$runner" ]] && ! command -v "$runner" >/dev/null 2>&1; then
  echo "error: '$runner' is not on PATH." >&2
  echo "       Install it (https://python-poetry.org/docs/#installation) and run" >&2
  echo "       'poetry install --with dev', or set CI_LOCAL_PYRUN=\"\" if you are" >&2
  echo "       already inside an activated virtualenv." >&2
  exit 2
fi

GATE_FAILED=()
ADVISORY_FAILED=()

# step <gate|advisory> "Name" cmd...
step() {
  local mode="$1"; local name="$2"; shift 2
  printf '\n\033[1m──▶ %s\033[0m' "$name"
  [[ "$mode" == advisory ]] && printf ' \033[2m(advisory)\033[0m'
  printf '\n'
  if "$@"; then
    printf '   \033[32m✓ %s\033[0m\n' "$name"
  else
    if [[ "$mode" == gate ]]; then
      printf '   \033[31m✗ %s (GATE)\033[0m\n' "$name"
      GATE_FAILED+=("$name")
    else
      printf '   \033[33m✗ %s (advisory — not a gate yet)\033[0m\n' "$name"
      ADVISORY_FAILED+=("$name")
    fi
  fi
}

# --- the checks -------------------------------------------------------------

# GATE: the full suite. Fast (~4s) and hermetic — no network, no config, no fixtures
# beyond tests/fixtures/. Coverage is on by default via addopts in pyproject.toml.
s_pytest() { $PYRUN pytest -q; }

# GATE (#73): the instruction/memory surface size guard. Hard-fails only on MEMORY.md at
# the harness truncation limit or CLAUDE.md over its ceiling; soft budgets warn. Warns
# rather than fails when the memory dir is absent, so a fresh clone is never blocked.
s_memory() { ./scripts/check-memory-budget.sh; }

# GATE: the version string lives in two places and they must agree. A mismatch is not
# caught by any test, and #66 records that `--version` reports the installed metadata
# version rather than the source __version__ — so the symptom is a confusing --version
# output at release time, not an error. Pure shell, so it works even without the runner.
s_version() {
  local pyproject init
  pyproject="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)"
  init="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/rdf_construct/__init__.py | head -1)"
  if [[ -z "$pyproject" || -z "$init" ]]; then
    echo "could not read a version string (pyproject.toml='$pyproject' __init__.py='$init')"
    return 1
  fi
  if [[ "$pyproject" != "$init" ]]; then
    echo "version mismatch: pyproject.toml=$pyproject but __init__.py=$init"
    return 1
  fi
  echo "version $pyproject (pyproject.toml and __init__.py agree)"
}

# GATE (#77): clean repo-wide as at 2026-08-22 — 142 of 142 files. `black` is also a
# pre-commit hook, so a failure here usually means the hook is not installed locally
# rather than a genuine surprise. On failure it prints the recovery command, because
# `black --check` names the files it would reformat but never what to run (#92). The
# hint is safe to follow: the black version is pinned exactly in pyproject.toml, so
# `black .` here and the hook agree about what "formatted" means.
s_black() {
  $PYRUN black --check . && return 0
  printf '   \033[2m→ fix: %s black .\033[0m\n' "$PYRUN"
  printf '   \033[2m  (if this keeps recurring, run `pre-commit install`)\033[0m\n'
  return 1
}

# ADVISORY (#78): 610 errors as at 2026-08-22, after the #77 sweep.
s_ruff() { $PYRUN ruff check .; }

# ADVISORY (#79): 296 errors in 51 files as at 2026-08-22, after the #77 sweep.
s_mypy() { $PYRUN mypy src/rdf_construct; }

# --- run --------------------------------------------------------------------

if [[ $RUN_TESTS -eq 1 ]]; then
  step gate "test suite (pytest)" s_pytest
fi
if [[ $RUN_OTHER -eq 1 ]]; then
  step gate     "version consistency"  s_version
  step gate     "memory-budget guard"  s_memory
  step gate     "black formatting"     s_black
  step advisory "ruff lint"            s_ruff
  step advisory "mypy type-check"      s_mypy
fi

# --- summary ----------------------------------------------------------------

printf '\n\033[1m── summary ─────────────────────────────\033[0m\n'
if (( ${#ADVISORY_FAILED[@]} )); then
  printf '  advisory issues (not gating): %s\n' "${ADVISORY_FAILED[*]}"
fi
if (( ${#GATE_FAILED[@]} )); then
  printf '  \033[31mGATE FAILED: %s\033[0m\n' "${GATE_FAILED[*]}"
  exit 1
fi
printf '  \033[32mgate green\033[0m%s\n' "$( (( ${#ADVISORY_FAILED[@]} )) && echo ' (with advisory warnings above)')"
