from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import (ABSTRACT_FILE, DEFAULT_TAG, LEAF_FILE, ROOT_ABSTRACT_FILE,
                     VALID_TAGS, Config, get_abstract_tree_dir,
                     parse_entry_value)
from .yaml_io import (is_child_abstract, is_root_abstract, load_yaml,
                      parse_root_abstract)

# ---------------------------------------------------------------------------
# Data structures produced by the walker
# ---------------------------------------------------------------------------


@dataclass
class FileEntry:
    """A file that should appear in the context output."""

    path: Path
    tag: str  # effective tag
    text_replacement: str | None  # if set, use this text instead of rendering
    file_cfg: dict[str, Any] | None  # symbol-level config dict (class:/def: keys)
    is_dir_entry: bool = False  # True for x_hard_abstract directory summaries


@dataclass
class WalkResult:
    """Result of walking a project directory."""

    root: Path
    config: Config
    files: list[FileEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _depth(path: Path, root: Path) -> int:
    """Number of directory components between root and path (0 = root itself)."""
    try:
        rel = path.relative_to(root)
        return len(rel.parts)
    except ValueError:
        return 0


def _dir_key(path: Path, root: Path) -> str:
    """Return the directory key as used in root abstract.yaml (e.g. 'src/auth/')."""
    try:
        rel = path.relative_to(root)
        parts = rel.parts
        return "/".join(parts) + "/"
    except ValueError:
        return str(path) + "/"


def _is_excluded_name(name: str, exclude_startswith: list[str]) -> bool:
    return any(name.startswith(prefix) for prefix in exclude_startswith)


def _is_excluded_folder(name: str, exclude_folders: list[str]) -> bool:
    return name in exclude_folders


def _has_extension(path: Path, extensions: list[str]) -> bool:
    # extensions list may contain entries like "py", "Dockerfile", "toml"
    ext = path.suffix.lstrip(".")
    name = path.name
    return ext in extensions or name in extensions


# ---------------------------------------------------------------------------
# Entry resolution
# ---------------------------------------------------------------------------


def _resolve_dir_entry(
    entry_val: Any,
    inherited_tag: str,
) -> tuple[str, str | None, dict[str, Any] | None]:
    """
    Resolve a directory entry value to (effective_tag, text_replacement, children).
    """
    tag, text, children = parse_entry_value(entry_val)

    if text is not None:
        # Terminal text replacement — directory skipped
        return "exclude", text, None

    effective_tag = tag if tag is not None else inherited_tag
    return effective_tag, None, children


def _resolve_file_entry(
    entry_val: Any,
    inherited_tag: str,
) -> tuple[str, str | None, dict[str, Any] | None]:
    """
    Resolve a file entry value to (effective_tag, text_replacement, file_cfg).
    """
    tag, text, children = parse_entry_value(entry_val)

    if text is not None:
        return inherited_tag, text, None

    effective_tag = tag if tag is not None else inherited_tag
    return effective_tag, None, children


# ---------------------------------------------------------------------------
# Root entries index
# ---------------------------------------------------------------------------


class RootEntriesIndex:
    """Index of root abstract.yaml entries by full relative directory path.

    Root entries can use multi-level paths like 'src/auth/' as keys.
    This index lets us look up the entry for any given directory.

    For a directory at relative path 'src/auth/', the key is 'src/auth/'.
    For inline file children of that directory, they live in the value dict.
    """

    def __init__(self, entries: dict[str, Any]) -> None:
        # dir_key -> entry value (may contain file children)
        self._dir_entries: dict[str, Any] = {}
        # top-level file entries (filename -> value) for files in project root
        self._root_file_entries: dict[str, Any] = {}

        for key, value in entries.items():
            if key.endswith("/"):
                # Old slash-notation format: "domain/users/"
                self._dir_entries[key] = value
            elif isinstance(value, dict) and value.get("is_dir") is True:
                # New dot-notation format: "domain.users" with is_dir: true
                # Convert "domain.users" → "domain/users/"
                slash_key = key.replace(".", "/") + "/"
                clean_value = {k: v for k, v in value.items() if k != "is_dir"}
                self._dir_entries[slash_key] = clean_value
            else:
                # Top-level file entry (file directly in project root)
                self._root_file_entries[key] = value

    @property
    def root_file_entries(self) -> dict[str, Any]:
        """File entries for files directly in the project root."""
        return self._root_file_entries

    def get_dir_entry(self, dir_key: str) -> Any:
        """Return the entry for a directory key, or None if not present."""
        return self._dir_entries.get(dir_key)

    def get_file_entries_for_dir(self, dir_key: str) -> dict[str, Any]:
        """Return file entries (filename -> value) for a given directory key."""
        entry_val = self._dir_entries.get(dir_key)
        if entry_val is None:
            return {}
        if not isinstance(entry_val, dict):
            return {}
        # File entries are non-abstract, non-directory keys
        _NON_FILE_KEYS = frozenset(
            {"abstract", "x_abstract", "parent-dirs", "x_hard_abstract"}
        )
        return {
            k: v
            for k, v in entry_val.items()
            if not k.endswith("/") and k not in _NON_FILE_KEYS
        }


# ---------------------------------------------------------------------------
# Main walker
# ---------------------------------------------------------------------------


class ProjectWalker:
    """Walk a project directory applying tag inheritance from abstract.yaml files."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load_root_abstract(self) -> tuple[Config, str, dict[str, Any]]:
        """Load and parse the root abstract.yaml. Returns (config, root_tag, entries)."""
        abstract_path = get_abstract_tree_dir(self.root) / ROOT_ABSTRACT_FILE
        data = load_yaml(abstract_path)

        if not data or not is_root_abstract(data):
            # No root abstract — use defaults
            return Config(), DEFAULT_TAG, {}

        config, root_tag, entries = parse_root_abstract(data)
        return config, root_tag or DEFAULT_TAG, entries

    def walk(self) -> WalkResult:
        """Walk the project and produce a WalkResult."""
        config, root_tag, root_entries = self.load_root_abstract()
        result = WalkResult(root=self.root, config=config)
        index = RootEntriesIndex(root_entries)

        self._walk_dir(
            directory=self.root,
            inherited_tag=root_tag,
            index=index,
            config=config,
            result=result,
            is_root=True,
            file_entries=index.root_file_entries,
        )
        return result

    def _load_leaf_abstract(self, directory: Path) -> dict[str, str]:
        """Load abstract-leaf.yaml from a directory.

        Returns a flat dict of name -> description string.
        Keys that start with any exclude_startswith prefix are ignored
        (user's way to deactivate an entry without deleting it).
        Only string values are included; other value types are ignored.
        """
        leaf_path = directory / LEAF_FILE
        if not leaf_path.exists():
            return {}
        data = load_yaml(leaf_path)
        if not data or not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if isinstance(v, str) and v}

    def _load_child_abstract(self, directory: Path) -> dict[str, Any] | None:
        """Load child abstract.yaml if present and depth matches."""
        child_path = directory / ABSTRACT_FILE
        if not child_path.exists():
            return None
        data = load_yaml(child_path)
        if not data:
            return None
        # Verify depth
        expected_depth = _depth(directory, self.root)
        if is_child_abstract(data, expected_depth):
            # Return only file entries — skip headers and directory entries
            _SKIP_KEYS = frozenset({"abstract-depth", "parent-dirs"})
            return {
                k: v
                for k, v in data.items()
                if k not in _SKIP_KEYS
                and not (isinstance(v, dict) and v.get("is_dir") is True)
            }
        return None

    def _walk_dir(
        self,
        directory: Path,
        inherited_tag: str,
        index: RootEntriesIndex,
        config: Config,
        result: WalkResult,
        is_root: bool = False,
        # file_entries: explicit file entries for this directory (from root index or child abstract)
        file_entries: dict[str, Any] | None = None,
    ) -> None:
        """Recursively walk a directory."""
        # Determine effective file entries for this directory:
        # Priority: child abstract.yaml > file_entries from root index

        effective_file_entries: dict[str, Any] = dict(file_entries or {})

        if not is_root and not config.is_flat:
            child_entries = self._load_child_abstract(directory)
            if child_entries is not None:
                # child abstract overrides root index entries for this directory
                # child format: filename -> value (no directory prefix)
                effective_file_entries = child_entries

        # Collect directory contents, sorted (dirs first by is_file key, then name)
        try:
            entries_in_dir = sorted(
                directory.iterdir(), key=lambda p: (p.is_file(), p.name)
            )
        except PermissionError:
            return

        # Load highest-priority leaf overrides for this directory
        leaf_overrides = self._load_leaf_abstract(directory)
        # Filter out deactivated keys (those starting with any exclude prefix)
        leaf_overrides = {
            k: v
            for k, v in leaf_overrides.items()
            if not _is_excluded_name(k, config.exclude_startswith)
        }

        for item in entries_in_dir:
            name = item.name

            # Skip abstract files
            if name in (ABSTRACT_FILE, ROOT_ABSTRACT_FILE, LEAF_FILE):
                continue

            # Skip excluded names
            if _is_excluded_name(name, config.exclude_startswith):
                continue

            if item.is_dir():
                if _is_excluded_folder(name, config.exclude_folders):
                    continue
                # Leaf override for a directory: emit virtual summary, skip walking
                if name in leaf_overrides:
                    result.files.append(
                        FileEntry(
                            path=item,
                            tag=inherited_tag,
                            text_replacement=leaf_overrides[name],
                            file_cfg=None,
                            is_dir_entry=True,
                        )
                    )
                    continue
                self._process_dir(item, inherited_tag, index, config, result)

            elif item.is_file():
                # Leaf override for a file: emit with text replacement, bypass extension filter
                if name in leaf_overrides:
                    result.files.append(
                        FileEntry(
                            path=item,
                            tag=inherited_tag,
                            text_replacement=leaf_overrides[name],
                            file_cfg=None,
                        )
                    )
                    continue
                if not _has_extension(item, config.include_extensions):
                    continue
                self._process_file(item, inherited_tag, effective_file_entries, result)

    def _process_dir(
        self,
        directory: Path,
        inherited_tag: str,
        index: RootEntriesIndex,
        config: Config,
        result: WalkResult,
    ) -> None:
        """Process a subdirectory."""
        dir_key = _dir_key(directory, self.root)
        entry_val = index.get_dir_entry(dir_key)

        if entry_val is not None:
            # Handle x_hard_abstract: directory-level absolute-priority description.
            # "off" means the feature is inactive — fall through to normal processing.
            if isinstance(entry_val, dict) and "x_hard_abstract" in entry_val:
                x_hard = entry_val["x_hard_abstract"]
                x_hard_str = str(x_hard).strip().strip('"').strip()
                if x_hard_str != "off":
                    # Active description: add a virtual summary entry, don't walk files
                    result.files.append(
                        FileEntry(
                            path=directory,
                            tag=inherited_tag,
                            text_replacement=x_hard_str,
                            file_cfg=None,
                            is_dir_entry=True,
                        )
                    )
                    return
                # "off" → fall through to normal directory processing

            effective_tag, text, _children = _resolve_dir_entry(
                entry_val, inherited_tag
            )

            if effective_tag == "exclude":
                return

            if text is not None:
                # Terminal text for directory — skip
                return

            # Get file entries for this directory from root index
            file_entries = index.get_file_entries_for_dir(dir_key)
        else:
            effective_tag = inherited_tag
            file_entries = {}

        self._walk_dir(
            directory=directory,
            inherited_tag=effective_tag,
            index=index,
            config=config,
            result=result,
            is_root=False,
            file_entries=file_entries,
        )

    def _process_file(
        self,
        file_path: Path,
        inherited_tag: str,
        dir_entries: dict[str, Any],
        result: WalkResult,
    ) -> None:
        """Process a file and add to result if not excluded."""
        name = file_path.name

        if name in dir_entries:
            entry_val = dir_entries[name]
            effective_tag, text, file_cfg = _resolve_file_entry(
                entry_val, inherited_tag
            )
        else:
            effective_tag = inherited_tag
            text = None
            file_cfg = None

        if effective_tag == "exclude":
            return

        result.files.append(
            FileEntry(
                path=file_path,
                tag=effective_tag,
                text_replacement=text,
                file_cfg=file_cfg,
            )
        )
