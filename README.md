# cxtree

[![PyPI](https://img.shields.io/pypi/v/cxtree)](https://pypi.org/project/cxtree/)
[![Python](https://img.shields.io/pypi/pyversions/cxtree)](https://pypi.org/project/cxtree/)
[![Tests](https://img.shields.io/github/actions/workflow/status/aiumi-net/cxtree/publish.yml?label=tests)](https://github.com/aiumi-net/cxtree/actions)
[![License](https://img.shields.io/github/license/aiumi-net/cxtree)](LICENSE)

> Generate focused, token-efficient LLM context files from your project.

`cxtree` walks a project directory, assembles source files into Markdown code
blocks and writes `context.md` — ready to paste into any LLM chat. When the
project is large it automatically splits into per-folder files.

![DEMO](/tests/app_1/demo.gif)

---

## Why

Pasting code into an LLM and hoping for the best is not a workflow. Deciding
*what* the LLM sees — and *why* — forces a clarity that makes every
conversation more precise and every answer more useful. `cxtree` makes that
decision explicit: one command generates the context, then `abstract-leaf.yaml`
files let you progressively annotate your project until the view reflects
exactly what matters for the task at hand. It takes some upfront effort.
Navigating a codebase together with an LLM, with full control over its view,
is worth it.

---

## Installation

```bash
pip install cxtree
# or
uv add cxtree
```

Requires Python 3.11+.

---

## Quick start

```bash
cd my-project
cxtree create     # writes context.md
                  # paste it into your LLM
```

---

## Commands

### `cxtree tree`

Print a coloured directory tree with line-budget percentages.

```
cxtree tree [-n N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-n` / `--max-lines` | `3000` | Line budget used to colour percentage labels |

Colours: **green** ≤ 80 %, **yellow** ≤ 90 %, **red** ≤ 100 %, **magenta** > 100 %.

If `abstract-tree.yaml` exists its `include_extensions` / `exclude_folders`
settings are applied to the tree.

---

### `cxtree create`

Generate `context.md` from the current directory.

```
cxtree create [-n N] [--code | --complete] [-f]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-n` / `--max-lines` | `3000` (or saved value) | Max lines per `context.md` before splitting |
| `--complete` | default | Verbatim file content |
| `--code` | | Strip docstrings; apply `# CX` markers |
| `-f` / `--folder` | | Store files in `.context-tree/` with rotation |

**What it writes:**

- `context.md` — at the project root (or `.context-tree/context.md` in folder mode)
- `_context.md` — in each overflowed sub-directory (normal mode)
- `abstract-tree.yaml` — project structure + saved config
- `abstract-leaf.yaml` — per-directory key/value index (see below)

**Overflow / splitting:**

When the total line count exceeds `-n`, `create` splits by immediate
sub-directories: each sub-directory gets its own `_context.md` (recursing as
needed). The root `context.md` contains only root-level files plus references
to the sub-contexts. Overflowed directories appear as `_context.md` in
`abstract-tree.yaml`.

**`-n` is remembered:**

The first time you pass `-n 500`, the value is saved in `abstract-tree.yaml`.
Subsequent `cxtree create` calls without `-n` reuse the saved value.

---

### `cxtree rm`

Remove all cxtree-generated artefacts.

```
cxtree rm
```

**Always removed:** `.context-tree/`, `abstract-tree.yaml`, all `context.md` files.

**Conditionally kept:** `abstract-leaf.yaml` files that contain user-written
summaries (any value other than `false`) are preserved so that documentation
committed to the repository is not lost.

---

## Render modes

### `--complete` (default)

File content is copied verbatim into the code block.

### `--code`

Docstrings are stripped from Python files. A docstring is **kept** when its
body contains the marker `# cxtree` (or `#cxtree`).

```python
def deploy():
    """
    Deploy to production.
    # cxtree  <- marker: keep this docstring
    """
    ...
```

**Inline markers** (work in both modes):

| Marker | Effect |
|--------|--------|
| `# CX` or `# cxtree` | Remove this line from the output |
| `# CX -N` or `# cxtree -N` | Remove the next N lines; insert `# ...` |

```python
SECRET_KEY = "abc123"  # CX

# cxtree -3
token = header[7:]
sig   = hmac.new(SECRET_KEY, token)
valid = sig == expected
```

---

## abstract-tree.yaml

Auto-generated at the project root. Contains a config header and a flat tree
of the project.

```yaml
cxtree:
  n: 3000
  include_extensions: [py, ts]
  exclude_startswith: [".", "__"]
  exclude_folders: [.venv, node_modules, __pycache__, .git, .context-tree]

_root:
  - main.py
  - pyproject.toml

src:
  - utils.py
  - models.py

src/api:
  - routes.py

domain: _context.md     # overflow: _context.md was created here
workers: _context.md
```

Edit `include_extensions` and `exclude_folders` to control which files are
included on subsequent runs. Everything else is informational.

---

## abstract-leaf.yaml

Created alongside each `context.md`. Keys are the immediate files and
sub-directories; values start as `false`.

```yaml
# src/abstract-leaf.yaml
utils.py: false
models.py: false
api/: false
```

**Adding summaries:**

Change a value from `false` to a string. On the next `cxtree create` run,
the summary replaces the actual file content — useful for reducing noise from
large or irrelevant modules.

```yaml
utils.py: "String helpers — no LLM context needed."
models.py: false
api/: false
```

**Summaries are picked up at every level:**

Sub-directory `abstract-leaf.yaml` files are always merged into the parent
context. If `domain/abstract-leaf.yaml` marks `users/: "User management"`,
that summary will appear in the root `context.md` regardless of overflow.

**Formatting is preserved:**

`cxtree create` never rewrites existing entries. New keys for newly added
files are appended to the end of the file. Commit `abstract-leaf.yaml` to the
repository as lightweight per-directory documentation.

---

## Folder mode (`-f`)

```bash
cxtree create -f
```

All context files are stored inside `.context-tree/` instead of scattered
across the project tree.

- `.context-tree/.gitignore` is created automatically.
- On each run, previous context files are rotated to `.context-tree/bin/<timestamp>/`.
- Bin folders older than 2 hours are deleted automatically.
- Once `.context-tree/` exists, folder mode is auto-activated on subsequent runs.

---

## Example workflow

```bash
cxtree create -n 2000        # first run — sets and saves budget
cxtree tree -n 2000          # explore with percentages

# annotate heavy directories in abstract-leaf.yaml, then:
cxtree create                # n=2000 is reused

cxtree rm                    # clean up (keeps leaf files with summaries)
cxtree create                # summaries are picked up automatically
```

---

## License

MIT
