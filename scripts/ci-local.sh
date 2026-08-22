#!/usr/bin/env bash
#
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
#   GATE     — the test suite, the version-consistency check and the instruction/memory
#              size guard. A gate step's failure IS this script's exit code.
#   ADVISORY — black, ruff and mypy. They run and report but do NOT fail the script,
#              because each carries substantial pre-existing debt measured across the
#              whole repository (see the tracking issues below). Gating on them today
#              would mean the script failed on every run from day one, and a check that
#              always fails is a check nobody reads.
#
# Keep the files YOUR change touches clean; you are not expected to fix the rest.
# When a debt lands at zero, flip its step from `advisory` to `gate` below — a
# one-word change — and, for black, restore its pre-commit hook.
#
#   black debt   — #77   ruff debt — #78   mypy --strict debt — #79
#
# Runs every selected check even if an earlier one fails, then prints a summary and
# exits non-zero iff a GATE step failed. Override the Python runner with CI_LOCAL_PYRUN
# (default "poetry run"; set to "" inside an already-active venv).
#
# Usage:
#   scripts/ci-local.sh              # gates (pytest + memory guard) + advisory (black, ruff, mypy)
#   scripts/ci-local.sh --tests-only # the pytest gate alone (fast)
#   scripts/ci-local.sh --lint-only  # the non-pytest checks (black, ruff, mypy, memory guard)
#   scripts/ci-local.sh -h|--help

set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || { echo "not in a git repo" >&2; exit 2; }

PYRUN="${CI_LOCAL_PYRUN-poetry run}"
RUN_TESTS=1
RUN_OTHER=1
case "${1-}" in
  --tests-only) RUN_OTHER=0 ;;
  --lint-only)  RUN_TESTS=0 ;;
  -h|--help)    sed -n '2,37p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

# ADVISORY (#77): 93 of 142 files would be reformatted as at 2026-08-22.
s_black() { $PYRUN black --check .; }

# ADVISORY (#78): 597 errors as at 2026-08-22.
s_ruff() { $PYRUN ruff check .; }

# ADVISORY (#79): 293 errors in 50 files as at 2026-08-22.
s_mypy() { $PYRUN mypy src/rdf_construct; }

# --- run --------------------------------------------------------------------

if [[ $RUN_TESTS -eq 1 ]]; then
  step gate "test suite (pytest)" s_pytest
fi
if [[ $RUN_OTHER -eq 1 ]]; then
  step gate     "version consistency"  s_version
  step gate     "memory-budget guard"  s_memory
  step advisory "black formatting"     s_black
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
