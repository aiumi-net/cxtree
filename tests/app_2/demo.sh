#!/usr/bin/env bash
# =============================================================================
# cxtree Demo — app_2 (large project)
#
# Demonstrates:  Overflow/splitting, folder mode, budget control, summaries
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
RED="\033[31m"
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

info() {
    echo -e "${DIM}Info:${RESET}         $1"
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

list_generated() {
    echo -e "${DIM}Generated files:${RESET}"
    find . \( -name "context.md" -o -name "_context.md" -o -name "abstract-tree.yaml" -o -name "abstract-leaf.yaml" \) \
        ! -path "./.context-tree/*" 2>/dev/null | sort | while read -r f; do
        local lines
        lines=$(wc -l < "$f")
        echo "  $f  (${lines} lines)"
    done
    if [ -d ".context-tree" ]; then
        echo -e "${DIM}  .context-tree/:${RESET}"
        find .context-tree -maxdepth 1 -type f | sort | while read -r f; do
            local lines
            lines=$(wc -l < "$f")
            echo "    $f  (${lines} lines)"
        done
    fi
    echo ""
}

# ---------------------------------------------------------------------------
# Setup — work in a tempdir so the repo stays clean
# ---------------------------------------------------------------------------

WORKDIR=$(mktemp -d)
# Copy everything except demo.sh and .env (secrets)
for item in "$SCRIPT_DIR"/*; do
    [ "$(basename "$item")" = "demo.sh" ] && continue
    cp -R "$item" "$WORKDIR/"
done
# Hidden files (e.g. .env) intentionally not copied —
# we want to show that cxtree works without .env
cd "$WORKDIR"

trap 'rm -rf "$WORKDIR"' EXIT

echo ""
echo -e "${BOLD}══════════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  cxtree Demo — app_2 (large project with API, Domain, Workers)${RESET}"
echo -e "${BOLD}  Working directory: $WORKDIR${RESET}"
echo -e "${BOLD}  Pause between steps: ${PAUSE}s${RESET}"
echo -e "${BOLD}══════════════════════════════════════════════════════════════════════${RESET}"

# ===== Step 1 =====
step "View project structure"
story "I have a large project (API + Domain + Workers + Core) and want to estimate its scope."
expect "Coloured tree — orange folders, blue .py files, percentage labels for the line budget."
$CXTREE tree -n 300
pause

# ===== Step 2 =====
step "Generate context.md with a large budget (everything in one file)"
story "I want to put everything into a single context.md first to see the total size."
expect "One large context.md with all files. No splitting because n=3000 is more than enough."
$CXTREE create -n 3000
echo ""
list_generated
show_file context.md 40
info "The entire codebase fits into one file at n=3000."
pause

# ===== Step 3 =====
step "Clean up and regenerate with a small budget (overflow/splitting)"
story "My LLM has a small context window. I set n=100 to trigger splitting."
expect "context.md at root + multiple _context.md in subdirectories. abstract-tree.yaml shows overflow."
$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 100
echo ""
list_generated
pause

# ===== Step 4 =====
step "Inspect root context.md in split mode"
story "I want to see how the root context.md references the sub-files."
expect "Only root-level files (main.py) plus references to _context.md in each subdirectory."
show_file context.md 30
pause

# ===== Step 5 =====
step "Inspect sub-context (domain/_context.md)"
story "I'm looking at one of the split files to verify the content is complete."
expect "All domain files (models.py, services.py, notifications/*) in their own context.md."
if [ -f domain/_context.md ]; then
    show_file domain/_context.md 40
else
    echo -e "${DIM}  domain/_context.md not present (budget was sufficient)${RESET}"
    echo ""
fi
pause

# ===== Step 6 =====
step "abstract-tree.yaml shows overflow structure"
story "I want to see which directories have overflowed."
expect "Directories with '_context.md' as value = own file. Lists = inline."
show_file abstract-tree.yaml
pause

# ===== Step 7 =====
step "Persist the n value"
story "n=100 is too small. I set n=200 and want cxtree to remember it."
expect "n=200 is saved in abstract-tree.yaml. Next run without -n reuses 200."
$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 200
echo ""
echo -e "${DIM}Saved n value:${RESET}"
grep "  n:" abstract-tree.yaml 2>/dev/null || grep "  n:" .context-tree/abstract-tree.yaml 2>/dev/null || true
echo ""

echo -e "${DIM}Second run without -n (abstract-tree.yaml stays, should reuse n=200):${RESET}"
# Only delete context files, abstract-tree.yaml remains
find . -name "context.md" -o -name "_context.md" | xargs rm -f 2>/dev/null || true
$CXTREE create
echo ""
echo -e "${DIM}n value after second run:${RESET}"
grep "  n:" abstract-tree.yaml 2>/dev/null || true
echo ""
list_generated
pause

# ===== Step 8 =====
step "Activate folder mode (-f)"
story "I don't want _context.md files scattered across the project tree — I want them centralized in .context-tree/."
expect "All context files land in .context-tree/ with flat names (e.g. domain_context.md)."
$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 200 -f
echo ""
list_generated
pause

# ===== Step 9 =====
step "Folder mode: verify rotation"
story "I run create again — the old files should be rotated into .context-tree/bin/."
expect "Previous context files are moved to a timestamped folder under bin/."
$CXTREE create
echo ""
echo -e "${DIM}.context-tree/bin/ contents:${RESET}"
find .context-tree/bin -type f 2>/dev/null | head -10 | sort
echo ""
info "Old versions are automatically deleted after 2 hours."
pause

# ===== Step 10 =====
step "Leaf summaries: summarize individual files"
story "The worker tasks are boilerplate — my LLM only needs a short description."
expect "workers/tasks/ gets summaries. context.md shows text instead of code."
$CXTREE rm > /dev/null 2>&1

# First create normally
$CXTREE create -n 3000 > /dev/null 2>&1

# Write summaries
mkdir -p workers/tasks
cat > workers/abstract-leaf.yaml << 'LEAF'
base.py: "BaseWorker ABC + WorkerPool (start/stop lifecycle, max_workers limit)."
tasks/: false
LEAF

cat > workers/tasks/abstract-leaf.yaml << 'LEAF'
cleanup.py: "CleanupWorker: periodic purge of expired sessions and soft-deleted users."
report.py: "ReportWorker: daily usage statistics reports via NotificationService."
LEAF

echo -e "${GREEN}Summaries written:${RESET}"
show_file workers/abstract-leaf.yaml
show_file workers/tasks/abstract-leaf.yaml

$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 3000
echo ""
echo -e "${DIM}Relevant excerpt from context.md (workers):${RESET}"
grep -A 2 -i "worker\|cleanup\|report" context.md | head -20 || true
echo ""
pause

# ===== Step 11 =====
step "Leaf summaries: summarize entire directories"
story "Now I collapse multiple directories to show only what's essential."
expect "domain/notifications/ and api/v1/ appear as one-line summaries."

cat > domain/abstract-leaf.yaml << 'LEAF'
models.py: false
services.py: false
notifications/: "Email and SMS dispatchers (EmailDispatcher, SmsDispatcher) with dispatch/broadcast."
LEAF

cat > api/abstract-leaf.yaml << 'LEAF'
routes.py: false
middleware.py: false
v1/: "REST API v1: User CRUD endpoints + Pydantic schemas (UserCreateRequest, UserResponse)."
LEAF

$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 3000
echo ""
show_file context.md 50
pause

# ===== Step 12 =====
step "Combination: summaries + splitting + folder mode"
story "Ultimate test — small budget (n=150), summaries active, folder mode."
expect "Splitting with summaries: summarized dirs stay inline, the rest gets split out."
$CXTREE rm > /dev/null 2>&1
$CXTREE create -n 150 -f
echo ""
list_generated
echo -e "${DIM}Root context.md:${RESET}"
show_file .context-tree/context.md 35

echo -e "${DIM}Tree with budget n=150:${RESET}"
$CXTREE tree -n 150
pause

# ===== Step 13 =====
step "Final cleanup"
story "I'm done and cleaning up everything."
expect "cxtree rm removes everything — but abstract-leaf.yaml files with summaries are preserved."
$CXTREE rm
echo ""
echo -e "${DIM}Remaining abstract-leaf.yaml files (with user summaries):${RESET}"
find . -name "abstract-leaf.yaml" 2>/dev/null | sort | while read -r f; do
    echo -e "  ${GREEN}$f${RESET}"
    sed 's/^/    /' "$f"
    echo ""
done

echo -e "${BOLD}${GREEN}Demo complete!${RESET}"
echo ""
