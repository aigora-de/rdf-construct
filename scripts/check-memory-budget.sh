#!/usr/bin/env bash
#
# check-memory-budget.sh — size guard for rdf-construct's instruction/memory surface.
#
# Copyright (c) 2026 Dave Dyke. MIT licence.
#
# The always-loaded steering files (CLAUDE.md, the project-memory MEMORY.md index and its
# topic files) drift towards carrying inline reference detail that should be *routed to*
# on demand. This is the guard that keeps them lean — the mechanical half of the router
# pattern (#73).
#
# It is a RITUAL script, not a CI lint, because the larger half of what it checks is LOCAL
# and unreachable from a hosted runner: the Claude Code project-memory directory under
# ~/.claude/projects/… (MEMORY.md, its topic files, archive/) exists only on the
# developer's machine. CLAUDE.md and docs/dev/EXPERTS.md are tracked and therefore
# lintable — those two are also wired into .pre-commit-config.yaml — but a guard covering
# only them would give false assurance while the part that actually drifts went unchecked.
# Run it by hand before opening or merging a PR that touched any of these files.
#
# The memory directory is derived from the repo's absolute path the way Claude Code mangles
# it (slashes -> dashes under ~/.claude/projects/), overridable via $RDF_CONSTRUCT_MEMORY_DIR.
#
# Exit status: 0 = all hard budgets OK (warnings allowed); 1 = a hard budget breached
# (MEMORY.md at/over the harness truncation limit — silent memory loss — or CLAUDE.md over
# its ceiling); 2 = usage error.

set -euo pipefail

# --- budgets (bytes) --------------------------------------------------------
CLAUDE_HARD=12288        # 12 KiB — hard ceiling for the always-loaded router
CLAUDE_SOFT=8192         # 8 KiB — router target; more than this is reference to route out
MEMORY_HARD=24400        # ~24.4 KiB — the harness silently TRUNCATES at/over this
MEMORY_SOFT=16384        # 16 KiB — MEMORY.md index target
TOPIC_SOFT=40960         # 40 KiB — a topic file this big wants a split or an archive
ARCHIVE_SOFT=153600      # 150 KiB — cold storage may be big, but not unbounded
EXPERTS_SOFT=40960       # 40 KiB — the routed-to persona file
DESC_SOFT=500            # chars — frontmatter `description:` one-liner cap
ENTRY_SOFT=350           # chars — a MEMORY.md index line; a POINTER, not a summary

# --- locate the surface -----------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
EXPERTS_MD="$REPO_ROOT/docs/dev/EXPERTS.md"
MEMDIR="${RDF_CONSTRUCT_MEMORY_DIR:-$HOME/.claude/projects/$(printf '%s' "$REPO_ROOT" | sed 's#/#-#g')/memory}"

warns=0
fails=0

bytes() { wc -c < "$1" | tr -d ' '; }
kib()   { awk -v b="$1" 'BEGIN{printf "%.1f", b/1024}'; }

echo "memory-budget guard"
echo "  repo:   $REPO_ROOT"
echo "  memory: $MEMDIR"
echo

# --- CLAUDE.md (tracked; loads every turn) ----------------------------------
if [[ -f "$CLAUDE_MD" ]]; then
  b="$(bytes "$CLAUDE_MD")"
  if (( b >= CLAUDE_HARD )); then
    echo "FAIL  CLAUDE.md $(kib "$b") KiB >= $(kib "$CLAUDE_HARD") KiB hard ceiling — route reference out"
    (( fails++ )) || true
  elif (( b >= CLAUDE_SOFT )); then
    echo "warn  CLAUDE.md $(kib "$b") KiB >= $(kib "$CLAUDE_SOFT") KiB router target (hard $(kib "$CLAUDE_HARD") KiB) — route reference out"
    (( warns++ )) || true
  else
    echo "ok    CLAUDE.md $(kib "$b") KiB (< $(kib "$CLAUDE_SOFT") KiB)"
  fi
else
  echo "warn  CLAUDE.md not found at $CLAUDE_MD"
  (( warns++ )) || true
fi

# --- docs/dev/EXPERTS.md (tracked; routed-to) -------------------------------
if [[ -f "$EXPERTS_MD" ]]; then
  b="$(bytes "$EXPERTS_MD")"
  if (( b >= EXPERTS_SOFT )); then
    echo "warn  docs/dev/EXPERTS.md $(kib "$b") KiB >= $(kib "$EXPERTS_SOFT") KiB — consider splitting"
    (( warns++ )) || true
  else
    echo "ok    docs/dev/EXPERTS.md $(kib "$b") KiB"
  fi
else
  echo "warn  docs/dev/EXPERTS.md not found — the router points at it"
  (( warns++ )) || true
fi

# --- the memory store (local; absent on a fresh clone) ----------------------
if [[ ! -d "$MEMDIR" ]]; then
  echo
  echo "warn  memory dir not found — skipping its checks (expected on a fresh clone)"
  (( warns++ )) || true
else
  echo

  # MEMORY.md: total size, and one line per memory
  mem_md="$MEMDIR/MEMORY.md"
  if [[ -f "$mem_md" ]]; then
    b="$(bytes "$mem_md")"
    if (( b >= MEMORY_HARD )); then
      echo "FAIL  MEMORY.md $(kib "$b") KiB >= $(kib "$MEMORY_HARD") KiB — the harness TRUNCATES here; memories are being lost"
      (( fails++ )) || true
    elif (( b >= MEMORY_SOFT )); then
      echo "warn  MEMORY.md $(kib "$b") KiB >= $(kib "$MEMORY_SOFT") KiB target (truncates at $(kib "$MEMORY_HARD") KiB)"
      (( warns++ )) || true
    else
      echo "ok    MEMORY.md $(kib "$b") KiB (< $(kib "$MEMORY_SOFT") KiB)"
    fi

    # index lines are pointers, not summaries
    while IFS= read -r line; do
      n="${#line}"
      (( n > ENTRY_SOFT )) || continue
      echo "warn  MEMORY.md index line $n chars > $ENTRY_SOFT — it is a pointer, not a summary: ${line:0:60}…"
      (( warns++ )) || true
    done < <(grep '^- \[' "$mem_md" || true)
  else
    echo "warn  MEMORY.md not found in $MEMDIR"
    (( warns++ )) || true
  fi

  # topic files: size + a greppable description
  while IFS= read -r f; do
    [[ "$(basename "$f")" == "MEMORY.md" ]] && continue
    b="$(bytes "$f")"
    rel="${f#"$MEMDIR"/}"
    if (( b >= TOPIC_SOFT )); then
      echo "warn  $rel $(kib "$b") KiB >= $(kib "$TOPIC_SOFT") KiB — split it, or rotate closed history into archive/"
      (( warns++ )) || true
    fi
    desc="$(sed -n 's/^description: *//p' "$f" | head -1)"
    if [[ -z "$desc" ]]; then
      echo "warn  $rel has no frontmatter description: — it is the greppable header"
      (( warns++ )) || true
    elif (( ${#desc} > DESC_SOFT )); then
      echo "warn  $rel description: ${#desc} chars > $DESC_SOFT"
      (( warns++ )) || true
    fi
  done < <(find "$MEMDIR" -maxdepth 1 -name '*.md' | sort)

  # archive/: cold storage, allowed to be large
  if [[ -d "$MEMDIR/archive" ]]; then
    while IFS= read -r f; do
      b="$(bytes "$f")"
      rel="${f#"$MEMDIR"/}"
      if (( b >= ARCHIVE_SOFT )); then
        echo "warn  $rel $(kib "$b") KiB >= $(kib "$ARCHIVE_SOFT") KiB — split the archive; never delete one"
        (( warns++ )) || true
      fi
    done < <(find "$MEMDIR/archive" -name '*.md' | sort)
  fi
fi

# --- summary ----------------------------------------------------------------
echo
if (( fails )); then
  echo "FAILED: $fails hard budget(s) breached, $warns warning(s)"
  exit 1
fi
if (( warns )); then
  echo "ok (with $warns warning(s))"
else
  echo "ok — the surface is within budget"
fi
