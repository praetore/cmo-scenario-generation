"""Local CMO install paths (not committed — see cmo_config.example.json)."""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB_DIR = REPO_ROOT / "DB"
CONFIG_FILE = REPO_ROOT / "cmo_config.json"
CONFIG_EXAMPLE = REPO_ROOT / "cmo_config.example.json"


def load_config():
    if not CONFIG_FILE.is_file():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {CONFIG_FILE}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{CONFIG_FILE} must contain a JSON object.")
    return data


def resolve_db_dir(explicit=None):
    """
    Directory containing CMO source .db3 files.

    Priority: explicit argument > cmo_config.json > env > repo DB/.
    """
    if explicit is not None:
        return Path(explicit).expanduser().resolve()

    cfg = load_config()
    db_dir = cfg.get("db_dir")
    if db_dir:
        return Path(db_dir).expanduser().resolve()

    install_dir = cfg.get("cmo_install_dir")
    if install_dir:
        return (Path(install_dir).expanduser().resolve() / "DB")

    env_db = os.environ.get("CMO_DB_DIR")
    if env_db:
        return Path(env_db).expanduser().resolve()

    env_install = os.environ.get("CMO_INSTALL_DIR")
    if env_install:
        return (Path(env_install).expanduser().resolve() / "DB")

    return LOCAL_DB_DIR.resolve()


def config_source_label():
    if CONFIG_FILE.is_file():
        return f"cmo_config.json ({CONFIG_FILE})"
    if os.environ.get("CMO_DB_DIR") or os.environ.get("CMO_INSTALL_DIR"):
        return "environment variable"
    if LOCAL_DB_DIR.is_dir() and any(LOCAL_DB_DIR.glob("*.db3")):
        return f"local {LOCAL_DB_DIR.name}/ folder"
    return "not configured (see README.md)"


def format_config_setup_hint():
    return (
        f"Configure databases: copy {CONFIG_EXAMPLE.name} to {CONFIG_FILE.name} "
        f"and set db_dir or cmo_install_dir to your CMO install. "
        f"Alternatively copy .db3 files into {LOCAL_DB_DIR.name}/."
    )
