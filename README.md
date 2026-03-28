# cxtree

[![PyPI](https://img.shields.io/pypi/v/cxtree)](https://pypi.org/project/cxtree/)
[![GitHub](https://img.shields.io/badge/github-aiumi--net%2Fcxtree-blue)](https://github.com/aiumi-net/cxtree)

> Generate focused, token-efficient LLM context files from your project.

`cxtree` walks a project directory and produces a structured Markdown file
containing the directory tree and relevant source files as code blocks — ready
to paste into any LLM chat as context.

The key idea: instead of dumping everything into the context window, you control
exactly what the LLM sees — per directory, per file, per class, per function —
using a YAML configuration file.

---

## Installation

```bash
pip install cxtree
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add cxtree
```

---

## Quick start

```bash
# 1. Generate abstract-tree.yaml in your project root
cxtree init

# 2. Edit abstract-tree.yaml to configure what the LLM sees (optional)

# 3. Generate context.md
cxtree create
```

Then paste `context.md` into any LLM chat.

---

## Commands

All commands accept `-r / --root` to point at a project directory other than `.`.

### `init`

Traverses the project, discovers files, and writes `abstract-tree.yaml` to the
project root. If a file already exists it is preserved — only new entries are
added.

```bash
cxtree init
cxtree init -r path/to/project
```

**`--folder` flag** — stores both `abstract-tree.yaml` and `context.md` inside a
`.abstract-tree/` subdirectory (which gets a `.gitignore` that excludes its
contents from git). Useful for keeping the project root clean.

```bash
cxtree init --folder
```

Switching between folder and normal mode re-runs automatically and cleans up the
previous location.

---

### `create`

Reads `abstract-tree.yaml` and generates `context.md`.

```bash
cxtree create
cxtree create -o docs/llm-context.md   # custom output path
```

---

### `leafs`

Splits the flat root `abstract-tree.yaml` into per-directory `abstract.yaml`
child files. Useful for large projects where many directories need fine-grained
control.

```bash
cxtree leafs
```

Each directory with file-level entries gets its own `abstract.yaml`. The root
file is reduced to directory stubs. Re-running `leafs` on an already-split
project merges changes back first, then re-splits.

---

### `flatten`

The reverse of `leafs`. Reads all child `abstract.yaml` files and merges their
entries back into the root file, then deletes them.

```bash
cxtree flatten             # flatten everything
cxtree flatten domain      # flatten only the domain/ subtree
cxtree flatten domain.users
```

---

### `tree`

Prints a coloured directory tree of the project respecting the same exclusion
rules as `init`.

```bash
cxtree tree
```

Folders are shown in yellow, `.py` files in blue, everything else in white.

---

### `rm`

Removes all generated files: `context.md`, `abstract-tree.yaml`, and all child
`abstract.yaml` files.

```bash
cxtree rm
```

---

## abstract-tree.yaml

`abstract-tree.yaml` is the root configuration file. It has two sections:

1. A `cxtree:` header block with project-wide settings.
2. Directory and file entries that control what the LLM sees.

### Header block

```yaml
cxtree:
  x_root: docs           # default tag for the whole project
  is_flat: true          # true = only root file used; false = leaf mode
  ext_found: [py, toml]  # written by init — informational only
  config:
    x_rm_empty_lines: false       # strip all blank lines from output
    x_rm_empty_lines_docs: true   # strip blank lines from doc-only sections
    include:
      x_extensions: [py]          # file extensions included in context
    exclude:
      x_startswith: [".", "__"]   # skip files/dirs starting with these prefixes
      x_folders: [".venv", "node_modules", "__pycache__"]
```

### Directory entries

Directories use dot-notation keys with `is_dir: true`. `init` generates these
automatically.

```yaml
domain:
  is_dir: true

domain.users:
  is_dir: true
  models.py: docs
  auth.py: include
```

### File entries

Files are nested under their directory key (or at root level for files in the
project root). The value controls what the LLM sees.

```yaml
domain.users:
  is_dir: true
  models.py: docs          # show docstrings only
  auth.py: include         # show full source
  legacy.py: exclude       # hide completely
  base.py: "Shared base classes — no details needed."  # replace with text
```

---

## Tags

Tags control how a file (or symbol) is rendered.

| Tag | What the LLM sees |
|---|---|
| `docs` | Docstrings only — code bodies are replaced with `# ...` |
| `code` | Code bodies only — docstrings are stripped |
| `include` | Full source: code + docstrings |
| `exclude` | Hidden — not included in context at all |

Tags are inherited top-down. The `x_root` value in the header is the starting
point; any entry without an explicit tag inherits from its parent.

---

## Symbol-level configuration

For Python files you can configure individual classes and functions.

```yaml
domain.users:
  is_dir: true
  auth.py:
    x_abstract:
      - "Authentication service — login, logout, token validation."
    class:
      AuthService:
        x_abstract:
          - "Handles login, logout and token validation."
        def:
          login: docs          # show docstring only
          logout: docs
          validate_token: include   # show full source
          _sign: exclude       # hide private helper
    def:
      create_token: docs
```

`__init__`, `__post_init__`, `__new__` and other lifecycle dunders are always
skipped — they are never emitted even with `include`.

`x_abstract` on a file or class sets a description shown above its content.
Use a list for multi-line descriptions:

```yaml
auth.py:
  x_abstract:
    - "Authentication service."
    - "Tokens are HMAC-signed. No external JWT library required."
```

---

## Text replacements

Assign any string to a directory or file entry to replace it entirely with that
text. No further content is shown.

```yaml
domain.legacy:
  is_dir: true
  old_service.py: "Deprecated. Superseded by domain.users.services."
```

Multiline replacement using a YAML list:

```yaml
domain.users:
  is_dir: true
  models.py:
    - "User entity with id, username, email, is_active, roles."
    - "Session entity binding a user_id to a token and expiry."
```

### `x_hard_abstract` (directory-level)

Setting `x_hard_abstract` on a directory entry replaces the entire directory
with a single summary line — no files inside are walked.

```yaml
workers:
  is_dir: true
  x_hard_abstract: "Background workers for cleanup and reporting."
```

Set it to `"off"` to disable the override without removing the key:

```yaml
workers:
  is_dir: true
  x_hard_abstract: "off"
```

---

## abstract-leaf.yaml

Place an `abstract-leaf.yaml` file inside any directory to provide the
highest-priority flat overrides for that directory. Entries here override
everything else — tags, symbol config, even the `include_extensions` filter.

```yaml
# domain/abstract-leaf.yaml
notifications: "Email and SMS dispatchers — not relevant for this task."
models.py: "User entity and Notification entity."
```

**Keys = filenames or subdirectory names** within that directory only.
Values must be plain strings.

To deactivate an entry without deleting it, prefix the key with `.` or `__`
(the default `exclude_startswith` prefixes):

```yaml
# disabled — notifications/ is walked normally
.notifications: "Email and SMS dispatchers — not relevant for this task."
```

`abstract-leaf.yaml` is never included in the context output itself.

---

## Inline source tags

Fine-tune what gets shown inside a function or method body using inline comments.

### `# ++` — show N lines from this point

The number of `+` characters determines how many lines are shown starting from
and including the tagged line. `# ++` = 2 lines, `# +++` = 3 lines, etc.

```python
def build_app(config: AppConfig) -> dict:
    user_svc = UserService(config.db_url)  # ++
    notif_svc = NotificationService(...)
    # ← both lines above are shown; rest of body is compressed to # ...
```

### `# ---` — hide N lines

The number of `-` characters determines how many lines are hidden. The tagged
line and the N−1 lines that follow are replaced by a single `# ---` placeholder.
`# ---` = 3 lines hidden, `# ----` = 4 lines, etc.

```python
def process(self, request: dict) -> dict:
    token = header[len(prefix):]  # ---
    request["_token"] = token     # ← this line is hidden (part of the 3)
    return request
```

Both tags preserve the indentation of the tagged line in the placeholder.

---

## Leaf mode (per-directory child files)

Run `leafs` to split the flat root file into one `abstract.yaml` per directory.
This is useful when many directories need independent, detailed configuration.

```
project/
├── abstract-tree.yaml        # root — directory stubs only
├── domain/
│   └── abstract.yaml         # file entries for domain/
└── api/
    └── abstract.yaml         # file entries for api/
```

Child `abstract.yaml` files use the same tag and symbol syntax. They are
identified by `abstract-depth:` (set automatically by `leafs`) which must match
the directory's actual depth from the project root.

### `x_is_flat` and `x_hard_abstract` in child abstracts

A subdirectory entry inside a child abstract can carry two control keys:

```yaml
# domain/abstract.yaml
abstract-depth: 1
parent-dirs: [domain]

users:
  is_dir: true
  x_is_flat: false          # false = keep its own child abstract
  x_hard_abstract: "off"    # placeholder — replace "off" with text to activate
```

- `x_is_flat: true` — merge this subdirectory back into the parent on the next
  `leafs` run instead of keeping its own child abstract.
- `x_hard_abstract: "<text>"` — replace the entire subdirectory with a summary
  in the context output. `"off"` = feature inactive.

---

## Folder mode

Use `--folder` to keep generated files out of the project root:

```bash
cxtree init --folder
cxtree create    # reads and writes inside .abstract-tree/
```

The `.abstract-tree/` directory contains:

```
.abstract-tree/
├── .gitignore          # excludes everything inside from git
├── abstract-tree.yaml
└── context.md
```

Switch back to normal mode by running `init` without `--folder`:

```bash
cxtree init       # deletes .abstract-tree/, writes to project root
```

---

## Example workflow

```bash
# Initial setup
cxtree init

# Review abstract-tree.yaml, tune tags and descriptions, then generate
cxtree create

# For large projects: split into per-directory files
cxtree leafs

# Edit individual abstract.yaml files in each directory, then regenerate
cxtree create

# Merge a subtree back (e.g. after simplifying domain/)
cxtree flatten domain

# Clean up everything
cxtree rm
```
