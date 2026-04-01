# cxtree

[![PyPI](https://img.shields.io/pypi/v/cxtree)](https://pypi.org/project/cxtree/)

> Generate focused, token-efficient LLM context files from your project.

`cxtree` walks a project directory, assembles source files into Markdown code
blocks and writes `context.md` -- ready to paste into any LLM chat. When the
project is large it automatically splits into per-folder files.

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
cxtree create          # writes context.md
# paste context.md into your LLM
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

Colours: **green** <= 80 %, **yellow** <= 90 %, **red** <= 100 %, **magenta** > 100 %.

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

- `context.md` -- at the project root (or `.context-tree/context.md` in folder mode)
- `_context.md` -- in each overflowed sub-directory (normal mode)
- `abstract-tree.yaml` -- project structure + saved config
- `abstract-leaf.yaml` -- per-directory key/value index (see below)

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

**Always removed:** `.context-tree/`, `abstract-tree.yaml`, all `context.md`
files.

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

**Inline markers** (work in both modes, applied to non-docstring code):

| Marker | Effect |
|--------|--------|
| `# CX` or `# cxtree` | Remove this line from the output |
| `# CX -N` or `# cxtree -N` | Remove the next N lines; insert `# ...` |

```python
SECRET_KEY = "abc123"  # CX          # <- line removed

# cxtree -3                           # <- next 3 lines replaced with # ...
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

domain: _context.md     # <- overflow: _context.md was created here
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

Change a value from `false` to a text string. On the next `cxtree create`
run, the summary is used in `context.md` instead of the actual file/directory
content -- useful for reducing noise from large or irrelevant modules.

```yaml
utils.py: "String helpers -- no LLM context needed."
models.py: false
api/: false
```

**Summaries are picked up at every level:**

Sub-directory `abstract-leaf.yaml` files are always merged into the parent
context. If `domain/abstract-leaf.yaml` marks `users/: "User management"`,
that summary will appear in the root `context.md` -- no matter whether the
project overflows or not. The original file content of `domain/users/` is
suppressed.

**Formatting is preserved:**

`cxtree create` never rewrites existing entries in `abstract-leaf.yaml`. If
you write a YAML block scalar, it stays a block scalar. New keys for newly
added files are appended to the end of the file.

**`cxtree rm` behaviour:**

- File is removed when every value is `false`.
- File is kept when any value is a non-empty string (user summary present).

This lets you commit `abstract-leaf.yaml` to the repository as lightweight
per-directory documentation.

---

## Folder mode (`-f`)

```bash
cxtree create -f
```

All context files are stored inside `.context-tree/` instead of scattered
across the project tree. Sub-directory context files use a flat naming
scheme with `_` as the path separator: `domain/users` -> `domain_users_context.md`.

- `.context-tree/.gitignore` is created automatically (`*` -- ignores all contents).
- On each run, previous context files are rotated to `.context-tree/bin/<timestamp>/`.
- Bin folders older than 2 hours are deleted automatically.
- Overflow links between files inside `.context-tree/` are bare filenames
  (e.g. `[domain_users_context.md](domain_users_context.md)`).
- Once `.context-tree/` exists, folder mode is **auto-activated** on subsequent
  runs even without `-f`.

---

## Example workflow

```bash
# First run
cxtree create -n 2000

# Explore the tree with percentages
cxtree tree -n 2000

# Edit abstract-leaf.yaml in heavy directories to add summaries
# Then re-generate (n=2000 is remembered)
cxtree create

# Clean up everything (keeps leaf files with summaries)
cxtree rm

# Re-run -- abstract-leaf.yaml summaries are picked up automatically
cxtree create
```

---

## License

MIT
