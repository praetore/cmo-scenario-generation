"""Download the official Windows luacheck.exe into tools/luacheck/ (repo-local only)."""

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

LUACHECK_VERSION = "1.2.0"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INSTALL_DIR = REPO_ROOT / "tools" / "luacheck"


def luacheck_exe_path(install_dir: Path | None = None) -> Path:
    base = install_dir or DEFAULT_INSTALL_DIR
    return base / "luacheck.exe"


def release_url(version: str = LUACHECK_VERSION) -> str:
    return (
        "https://github.com/lunarmodules/luacheck/releases/download/"
        f"v{version}/luacheck.exe"
    )


def install_luacheck_local(
    version: str = LUACHECK_VERSION,
    install_dir: Path | None = None,
    *,
    quiet: bool = False,
) -> Path:
    """Download luacheck.exe; does not modify system PATH."""
    if sys.platform != "win32":
        raise OSError(
            "luacheck.exe is only bundled for Windows; install luacheck on PATH on Linux/macOS."
        )
    dest_dir = install_dir or DEFAULT_INSTALL_DIR
    dest = dest_dir / "luacheck.exe"
    url = release_url(version)
    if not quiet:
        print(f"Downloading luacheck v{version} ...", file=sys.stderr)
        print(f"  {url}", file=sys.stderr)
    dest_dir.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    if not dest.is_file():
        raise OSError(f"download incomplete: {dest}")
    proc = subprocess.run(
        [str(dest), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise OSError(f"luacheck.exe failed to run: {detail or proc.returncode}")
    if not quiet:
        out = (proc.stdout or proc.stderr or "").strip()
        if out:
            print(out, file=sys.stderr)
        print(f"Installed (repo-local): {dest}", file=sys.stderr)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download luacheck.exe to tools/luacheck/ (no PATH changes)."
    )
    parser.add_argument("--version", default=LUACHECK_VERSION, help="Luacheck release tag")
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help="Target directory (default: <repo>/tools/luacheck)",
    )
    args = parser.parse_args()
    try:
        install_luacheck_local(version=args.version, install_dir=args.install_dir)
    except OSError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
