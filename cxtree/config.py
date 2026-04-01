from __future__ import annotations

from dataclasses import dataclass, field

CONTEXT_TREE_DIR = ".context-tree"
ABSTRACT_TREE_FILE = "abstract-tree.yaml"
ABSTRACT_LEAF_FILE = "abstract-leaf.yaml"
CONTEXT_FILE = "context.md"  # root-level context file
SUBCONTEXT_FILE = "_context.md"  # per-subdirectory context file (normal mode)
DEFAULT_N = 3000

_DEFAULT_EXCLUDE_FOLDERS = [
    ".venv",
    "node_modules",
    "__pycache__",
    ".git",
    ".context-tree",
    ".pytest_cache",
    ".mypy_cache",
]


@dataclass
class Config:
    n: int = DEFAULT_N
    extensions_found: list[str] = field(default_factory=list)
    include_extensions: list[str] = field(default_factory=lambda: ["py"])
    exclude_startswith: list[str] = field(default_factory=lambda: [".", "__"])
    exclude_folders: list[str] = field(
        default_factory=lambda: list(_DEFAULT_EXCLUDE_FOLDERS)
    )

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        return cls(
            n=int(d.get("n", DEFAULT_N)),
            extensions_found=list(d.get("extensions_found", [])),
            include_extensions=list(d.get("include_extensions", ["py"])),
            exclude_startswith=list(d.get("exclude_startswith", [".", "__"])),
            exclude_folders=list(d.get("exclude_folders", _DEFAULT_EXCLUDE_FOLDERS)),
        )

    def to_dict(self) -> dict:
        d: dict = {"n": self.n}
        if self.extensions_found:
            d["extensions_found"] = self.extensions_found
        d["include_extensions"] = self.include_extensions
        d["exclude_startswith"] = self.exclude_startswith
        d["exclude_folders"] = self.exclude_folders
        return d
