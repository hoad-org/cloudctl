#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
create_manifest.py — Verifiable, low-noise repo-context manifest from ./tools

Purpose:
- Scan the repo root one level up from ./tools.
- Emit a compact, deterministic manifest file at ./tools/output/repo_context_manifest.txt.
- Exclude build artifacts, caches, venvs, egg-info, and large helper dumps like tree.txt.
- Include only source, config, docs, scripts, and examples likely needed for code review.

Key fixes in this revision:
- Exclude the repo-local smoke venv `.venv_smoke` and any directory starting with `.venv` or `venv`.
- Keep robust handling for paths outside the repo and timezone-aware timestamps.
- Use timezone.utc instead of datetime.UTC for Python < 3.11 compatibility.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import sys
from datetime import datetime, timezone  # Import timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent  # scan up one level (repo root)
OUTPUT_SUBDIR = SCRIPT_DIR / "output"
OUTPUT_FILENAME = "repo_context_manifest.txt"
OUTPUT_FILE = OUTPUT_SUBDIR / OUTPUT_FILENAME

# --------------------------------------------------------------------
# Targets for this repo (derived from actual tree)
# --------------------------------------------------------------------
TARGET_DIRS = [
    ".",  # project root files
    "awsctl",
    "tests",
    "scripts",
    "examples",
]

# --------------------------------------------------------------------
# Directory and file exclusions
# --------------------------------------------------------------------
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    ".terraform",
    ".venv",  # generic venv
    "venv",  # generic venv
    ".venv_smoke",  # smoke venv created by scripts/full_smoke.sh
    "awsctl/venv",
    "tools/output",  # our output area
}
# Any directory NAME that starts with one of these prefixes will be excluded
EXCLUDE_DIR_PREFIXES = (".venv", "venv")

# Any path element ending with one of these suffixes is excluded
EXCLUDE_DIR_SUFFIXES = (".egg-info",)

# Individual files to drop no matter where they are
GLOBAL_EXCLUDE_BASENAMES = {
    "manifest_full.txt",  # any legacy manifest name
    OUTPUT_FILENAME,  # our current output
    "tree.txt",  # helper dump, not needed
}

# --------------------------------------------------------------------
# Inclusion patterns (broad enough for real work, narrow enough to avoid noise)
# --------------------------------------------------------------------
INCLUDE_PATTERNS = [
    # source
    "*.py",
    # config and tooling
    "*.toml",
    "*.ini",
    "*.cfg",
    "*.yml",
    "*.yaml",
    # docs and metadata
    "*.md",
    "*.txt",
    # shell scripts and make targets
    "*.sh",
    "Makefile",
    # known top-level project files
    "README.md",
    "pyproject.toml",
    "tox.ini",
    "pytest.ini",
    "orgs.yaml",
    # examples
    "examples/*.yaml",
]

# --------------------------------------------------------------------
# AI usage preamble (written at the TOP of the manifest file)
# --------------------------------------------------------------------
AI_USAGE_PREAMBLE = f"""# 📦 Repo Context Manifest
Generated: {datetime.now(timezone.utc).isoformat()}
Root: {PROJECT_ROOT}

## How to use this manifest
Treat the MANIFEST block as the index, then use the FILE-START/END blocks as full-file sources.
Output full-file replacements when modifying code. Do not emit snippets.
"""


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _rel_to_root(path: Path) -> str | None:
    """Return repo-relative posix path, or None if the resolved path is outside the repo root."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except Exception:
        return None


def _under_any_excluded_dir(path: Path) -> bool:
    """
    True if path is under any excluded dir by explicit name, prefix, or suffix.
    If the path resolves outside the repo root, exclude it.
    """
    rel = _rel_to_root(path)
    if rel is None:
        return True  # exclude anything resolving outside the repo

    parts = Path(rel).parts
    # Build progressive prefixes: "a", "a/b", "a/b/c", ...
    prefixes = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]

    # Explicit directory exclusions
    if any(p in EXCLUDE_DIRS for p in prefixes):
        return True

    # Prefix name exclusions like ".venv*", "venv*"
    if any(any(seg.startswith(pref) for pref in EXCLUDE_DIR_PREFIXES) for seg in parts):
        return True

    # Suffix exclusions like "*.egg-info"
    if any(seg.endswith(EXCLUDE_DIR_SUFFIXES) for seg in parts):
        return True

    return False


def _matches_include_patterns(path: Path) -> bool:
    """Basename and simple subpattern checks against INCLUDE_PATTERNS."""
    rel = _rel_to_root(path)
    if rel is None:
        return False
    name = Path(rel).name
    for pattern in INCLUDE_PATTERNS:
        # allow simple directory/file globs like "examples/*.yaml"
        if "/" in pattern:
            if fnmatch.fnmatchcase(rel, pattern):
                return True
        else:
            if fnmatch.fnmatchcase(name, pattern):
                return True
    return False


def _should_include_file(path: Path) -> bool:
    """Final inclusion logic."""
    if path.name in GLOBAL_EXCLUDE_BASENAMES:
        return False
    if path.resolve() == OUTPUT_FILE.resolve():
        return False
    if _under_any_excluded_dir(path):
        return False
    return _matches_include_patterns(path)


def _safe_text(bytes_data: bytes) -> str:
    """Decode bytes to text with fallbacks."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return bytes_data.decode(enc)
        except UnicodeDecodeError:
            continue
    return repr(bytes_data)


def _hash_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _walk_targets() -> list[Path]:
    """Walk TARGET_DIRS from PROJECT_ROOT and return candidate files."""
    files: list[Path] = []
    for target in TARGET_DIRS:
        base = (PROJECT_ROOT / target).resolve()
        if not base.exists() or not base.is_dir():
            continue
        for root, dirs, fnames in os.walk(base, followlinks=False):
            # Prune dirs by name/prefix/suffix rules
            kept_dirs = []
            for d in dirs:
                d_full = Path(root) / d
                if _under_any_excluded_dir(d_full):
                    continue
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            for fname in sorted(fnames):
                p = Path(root) / fname
                if _should_include_file(p):
                    files.append(p)

    # De-duplicate by repo-relative path
    seen_rel = set()
    unique: list[Path] = []
    for p in files:
        rel = _rel_to_root(p)
        if rel and rel not in seen_rel:
            seen_rel.add(rel)
            unique.append(p)

    # Sort deterministically by repo-relative path
    unique.sort(key=lambda q: _rel_to_root(q) or "")
    return unique


def create_manifest() -> None:
    # Ensure output dir exists
    OUTPUT_SUBDIR.mkdir(parents=True, exist_ok=True)

    # Delete any previous output before scanning to avoid self-inclusion
    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

    # Collect files
    selected = _walk_targets()

    # Build manifest list and file blocks
    manifest_entries: list[dict[str, Any]] = []
    file_blocks: list[str] = []

    for f in selected:
        rel = _rel_to_root(f)
        if rel is None:
            continue
        b = f.read_bytes()
        s = _hash_bytes(b)
        t = _safe_text(b)
        lines = 0 if not t else t.count("\n") + (1 if t and not t.endswith("\n") else 0)
        entry = {
            "path": rel,
            "lines": lines,
            "bytes": len(b),
            "sha256": s,
            "parts": 1,
        }
        manifest_entries.append(entry)
        header = (
            f"---FILE-START: {rel} | LINES: {entry['lines']} | BYTES: {entry['bytes']} | "
            f"SHA256: {entry['sha256']}"
        )
        footer = f"---FILE-END: {rel}"
        content = t if t.strip() else "[EMPTY FILE CONTENT]"
        file_blocks.append(f"\n\n{header}\n{content}\n{footer}")

    manifest_json = json.dumps({"files": manifest_entries}, indent=2)
    final_output = (
        AI_USAGE_PREAMBLE
        + f"---MANIFEST-START---\n{manifest_json}\n---MANIFEST-END---"
        + "".join(file_blocks)
    )

    OUTPUT_FILE.write_text(final_output, encoding="utf-8")

    # Console summary
    total_bytes = sum(e["bytes"] for e in manifest_entries)
    print(f"✅ Manifest written: {OUTPUT_FILE}")
    print(f"📄 Files indexed: {len(manifest_entries)}  Size: {total_bytes/1024:.2f} KB")


if __name__ == "__main__":
    try:
        create_manifest()
    except Exception as e:
        print(f"❌ Failed to create manifest: {e}", file=sys.stderr)
        sys.exit(1)
