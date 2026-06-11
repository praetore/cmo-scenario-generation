"""Generate domain — paths, shared regex, path helpers."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
GENERATED_DIR = REPO_ROOT / "generated"
SOURCE_DIR = GENERATED_DIR / "src"
BOOTSTRAP_PATH = SCRIPTS_DIR / "scenario_bootstrap.lua"
SOURCE_SUFFIX = "_src"

DOFILE_LOADER = re.compile(
    r"(?:--[^\n]*\n)*?"
    r"local\s+CMO_SCENARIO_REPO\s*=\s*\[\[.*?\]\]\s*\n"
    r"local\s+bootstrap_ok\s*,\s*bootstrap_err\s*=\s*pcall\s*\(\s*dofile\s*,[^\n]+\)\s*\n"
    r"if\s+not\s+bootstrap_ok\s+then\s*\n"
    r"(?:.*\n)*?"
    r"^\s*return\s*\n"
    r"\s*end\s*\n",
    re.MULTILINE,
)

SINGLE_INLINED = re.compile(
    r"(?:-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n)?.*?^local M\s*=\s*\{.*?^cmo\s*=\s*M\s*\n",
    re.MULTILINE | re.DOTALL,
)

INLINED_MARKER = re.compile(
    r"^-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n",
    re.MULTILINE,
)
CMO_ASSIGN = re.compile(r"^cmo\s*=\s*M\s*$", re.MULTILINE)
FUNCTION_M = re.compile(r"^function M\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
CONST_M = re.compile(r"^M\.([A-Z][A-Z0-9_]*)\s*=")
ALIAS_M = re.compile(r"^M\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*M\.([A-Za-z_][A-Za-z0-9_]*)")
M_MEMBER = re.compile(r"\bM\.([A-Za-z_][A-Za-z0-9_]*)")
CMO_ENTRY = re.compile(r"\bcmo\.([A-Za-z_][A-Za-z0-9_]*)")
ALIAS_ENTRY = re.compile(
    r"local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*cmo\.([A-Za-z_][A-Za-z0-9_]*)"
)
AUTHORING_COMMENT = re.compile(
    r"^--\s*(?:SOURCE — do not load|Preflight:\s*python scripts/validate_scenario|"
    r"CMO load:|Bootstrap:\s*scripts/scenario_bootstrap)",
    re.IGNORECASE,
)
TOOLING_IN_COMMENT = re.compile(
    r"^\s*(?:--\s*)?(?:CMO|Preflight):\s*python scripts/(?:generate_scenario|embed_bootstrap|validate_scenario)",
    re.IGNORECASE,
)


def repo_relative(path: Path) -> str:
    """Path relative to repository root, forward slashes (for Lua headers)."""
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def is_source_scenario_path(path: Path) -> bool:
    stem = path.stem
    if stem.endswith("_import"):
        stem = stem[: -len("_import")]
    return stem.endswith(SOURCE_SUFFIX)


def embedded_scenario_path(source_path: Path) -> Path:
    """Map ``generated/src/foo_src.lua`` → ``generated/foo.lua`` (CMO load file)."""
    stem = source_path.stem
    if stem.endswith("_import"):
        stem = stem[: -len("_import")]
    if stem.endswith(SOURCE_SUFFIX):
        stem = stem[: -len(SOURCE_SUFFIX)]
    return GENERATED_DIR / f"{stem}{source_path.suffix}"


def source_scenario_path(any_path: Path) -> Path:
    """Map ``generated/foo.lua`` → ``generated/src/foo_src.lua``."""
    stem = any_path.stem
    if stem.endswith("_import"):
        stem = stem[: -len("_import")]
    if stem.endswith(SOURCE_SUFFIX):
        name = any_path.name
    else:
        name = f"{stem}{SOURCE_SUFFIX}{any_path.suffix}"
    return SOURCE_DIR / name


def ensure_source_dir() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)


def relocate_legacy_source(path: Path) -> Path:
    """Move ``generated/<name>_src.lua`` into ``generated/src/`` if needed."""
    path = path.resolve()
    if path.parent == SOURCE_DIR.resolve():
        return path
    if path.parent == GENERATED_DIR.resolve() and is_source_scenario_path(path):
        ensure_source_dir()
        dest = SOURCE_DIR / path.name
        if dest.resolve() != path:
            if dest.is_file():
                path.unlink()
            else:
                shutil.move(str(path), str(dest))
            print(f"Relocated source -> {repo_relative(dest)}")
        return dest.resolve()
    return path


def resolve_source_input(arg: str) -> Path | None:
    """Resolve CLI argument to an existing ``generated/src/*_src.lua`` file."""
    raw = Path(arg)
    candidates: list[Path] = []
    if raw.is_file():
        candidates.append(raw.resolve())
    candidates.extend(
        [
            (SOURCE_DIR / raw.name).resolve(),
            (SOURCE_DIR / raw).resolve(),
            (GENERATED_DIR / raw.name).resolve(),
            raw.resolve(),
        ]
    )
    seen: set[Path] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if cand.is_file() and is_source_scenario_path(cand):
            return relocate_legacy_source(cand)
    return None


def canonical_scenario_path(path: Path) -> Path:
    """Resolve generate output path from a source path."""
    if is_source_scenario_path(path):
        return embedded_scenario_path(path)
    stem = path.stem
    if stem.endswith("_import"):
        return path.with_name(f"{stem[: -len('_import')]}{path.suffix}")
    return path
