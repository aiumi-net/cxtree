#!/usr/bin/env bash
# =============================================================================
# cxtree Demo — app_1 (small project)
#
# Demonstrates:  Basics, --code vs --complete, CX markers, leaf summaries
# Usage:         ./demo.sh [PAUSE_SECONDS]
# Example:       ./demo.sh 5       # 5s pause between steps
#                ./demo.sh 0       # no pauses
# =============================================================================
set -euo pipefail

PAUSE="${1:-3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CXTREE="uv run --project $PROJECT_ROOT cxtree"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOLD="\033[1m"
DIM="\033[2m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
MAGENTA="\033[35m"
RESET="\033[0m"
SEPARATOR="${DIM}$(printf '%.0s─' {1..72})${RESET}"

step_nr=0
step() {
    step_nr=$((step_nr + 1))
    echo ""
    echo -e "$SEPARATOR"
    echo -e "${BOLD}${CYAN}Step $step_nr${RESET}${BOLD} — $1${RESET}"
    echo -e "$SEPARATOR"
    echo ""
}

story() {
    echo -e "${MAGENTA}User Story:${RESET}  $1"
}

expect() {
    echo -e "${YELLOW}Expected:${RESET}    $1"
    echo ""
}

pause() {
    if [ "$PAUSE" -gt 0 ] 2>/dev/null; then
        echo -e "${DIM}⏳ Pause ${PAUSE}s ...${RESET}"
        sleep "$PAUSE"
    fi
}

show_file() {
    local file="$1"
    local max_lines="${2:-30}"
    if [ -f "$file" ]; then
        local total
        total=$(wc -l < "$file")
        echo -e "${GREEN}── $file (${total} lines) ──${RESET}"
        head -n "$max_lines" "$file"
        if [ "$total" -gt "$max_lines" ]; then
            echo -e "${DIM}  ... ($((total - max_lines)) more lines)${RESET}"
        fi
    else
        echo -e "${DIM}  (file does not exist: $file)${RESET}"
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Setup — work in a tempdir so the repo stays clean
# ---------------------------------------------------------------------------

WORKDIR=$(mktemp -d)
cp -R "$SCRIPT_DIR"/* "$WORKDIR/"
cp -R "$SCRIPT_DIR"/.[!.]* "$WORKDIR/" 2>/dev/null || true
# don't copy demo.sh itself
rm -f "$WORKDIR/demo.sh"
cd "$WORKDIR"

trap 'rm -rf "$WORKDIR"' EXIT

echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  cxtree Demo — app_1 (small project with Auth + Permissions)${RESET}"
echo -e "${BOLD}  Working directory: $WORKDIR${RESET}"
echo -e "${BOLD}  Pause between steps: ${PAUSE}s${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════════════${RESET}"

# ===== Step 1 =====
step "Show project structure"
story "I have a small Python project and want to see what it looks like first."
expect "A coloured directory tree with percentage labels relative to the line budget."
$CXTREE tree -n 200
pause

# ===== Step 2 =====
step "Generate context.md (--complete, default)"
story "I want to create a context file with the full source code for my LLM."
expect "A context.md containing the complete content of all .py files, including docstrings."
$CXTREE create -n 3000
echo ""
show_file context.md 50
pause

# ===== Step 3 =====
step "Inspect abstract-tree.yaml"
story "I want to see what configuration and structure cxtree has detected."
expect "YAML with the cxtree config (n, extensions, excludes) and the project structure."
show_file abstract-tree.yaml
pause

# ===== Step 4 =====
step "Clean up and regenerate in --code mode"
story "The context.md is too long — my LLM doesn't need docstrings. I've also placed CX markers to hide secrets."
expect "Shorter context.md: docstrings removed, lines with '# CX' replaced by '# ...', secret blocks skipped."
$CXTREE rm
echo -e "${GREEN}Cleaned.${RESET}"
echo ""

echo -e "${DIM}Note — these CX markers are in the source code:${RESET}"
echo "  main.py:       '# CX -3'  (hide 3 import lines)"
echo "  main.py:       '# CX -2'  (hide login details)"
echo "  main.py:       '# cxtree' (keep this docstring!)"
echo "  permissions.py: '# cxtree -4' (hide 4 lines with secrets)"
echo "  permissions.py: '# cxtree' in docstring (keep docstring!)"
echo "  config.py:     '# CX'    (remove secret key line)"
echo ""

$CXTREE create --code -n 3000
echo ""
show_file context.md 60
pause

# ===== Step 5 =====
step "Compare: lines in --complete vs --code"
story "I want to see how much shorter code mode actually is."
expect "Significantly fewer lines because docstrings and marked blocks were removed."
CODE_LINES=$(wc -l < context.md)
$CXTREE rm > /dev/null 2>&1
$CXTREE create --complete -n 3000 > /dev/null 2>&1
COMPLETE_LINES=$(wc -l < context.md)
echo "  --complete: ${COMPLETE_LINES} lines"
echo "  --code:     ${CODE_LINES} lines"
echo "  Saved:      $((COMPLETE_LINES - CODE_LINES)) lines ($((100 - CODE_LINES * 100 / COMPLETE_LINES))%)"
echo ""
$CXTREE rm > /dev/null 2>&1
pause

# ===== Step 6 =====
step "Add leaf summaries"
story "My LLM doesn't need the auth code in detail — a short description is enough."
expect "Create abstract-leaf.yaml, add summaries for auth.py/base.py, context.md shows summaries instead of code."

# First create normally so abstract-leaf.yaml is generated
$CXTREE create -n 3000 > /dev/null 2>&1
echo -e "${DIM}Default abstract-leaf.yaml (all false):${RESET}"
show_file abstract-leaf.yaml 20

# Manually add summaries
cat > domain/users/abstract-leaf.yaml << 'LEAF'
auth.py: |
  AuthService: Login with HMAC-SHA256 token signing.
  Methods: login(), logout(), validate_token().
models.py: false
permissions.py: false
LEAF

cat > domain/abstract-leaf.yaml << 'LEAF'
base.py: "Entity base class with ID-based equality and in-memory Repository."
users/: false
LEAF

echo -e "${GREEN}Summaries written:${RESET}"
echo ""
echo -e "${DIM}domain/abstract-leaf.yaml:${RESET}"
show_file domain/abstract-leaf.yaml
echo -e "${DIM}domain/users/abstract-leaf.yaml:${RESET}"
show_file domain/users/abstract-leaf.yaml
pause

# ===== Step 7 =====
step "Regenerate with summaries"
story "Now cxtree should use the summaries — auth.py and base.py should appear as text only."
expect "context.md shows only the summary texts for auth.py/base.py, not the source code."
$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 3000
echo ""
show_file context.md 60
pause

# ===== Step 8 =====
step "Summarize an entire subdirectory"
story "The users/ directory is well documented — I'll collapse it into a single summary."
expect "context.md shows just one line for domain/users/ instead of all individual files."

cat > domain/abstract-leaf.yaml << 'LEAF'
base.py: "Entity base class with ID-based equality and in-memory Repository."
users/: "User domain: Auth (HMAC-SHA256), Models (User/Session), Permissions (RBAC)."
LEAF

$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 3000
echo ""
show_file context.md 40
pause

# ===== Step 9 =====
step "Final tree and cleanup"
story "I'm done — one last look at the tree, then clean up."
expect "Tree shows the structure. cxtree rm removes everything — but abstract-leaf.yaml files with summaries are preserved."
$CXTREE tree -n 200
echo ""
$CXTREE rm
echo ""
echo -e "${DIM}Files still present:${RESET}"
find . -name "abstract-leaf.yaml" -exec echo "  {}" \;
echo ""

echo -e "${BOLD}${GREEN}Demo complete!${RESET}"
echo ""
