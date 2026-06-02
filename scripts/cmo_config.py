"""Local CMO install paths (not committed — see cmo_config.example.ini)."""

import configparser
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB_DIR = REPO_ROOT / "DB"
CONFIG_FILE = REPO_ROOT / "cmo_config.ini"
CONFIG_EXAMPLE = REPO_ROOT / "cmo_config.example.ini"


def load_config():
    if not CONFIG_FILE.is_file():
        return {}
    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE, encoding="utf-8")
    if "cmo" not in parser:
        raise ValueError(f"{CONFIG_FILE} must contain a [cmo] section.")
    return dict(parser["cmo"])


def resolve_db_dir(explicit=None):
    """
    Directory containing CMO source .db3 files.

    Priority: explicit argument > cmo_config.ini > env > repo DB/.
    """
    if explicit is not None:
        return Path(explicit).expanduser().resolve()

    cfg = load_config()
    install_dir = cfg.get("cmo_install_dir")
    if install_dir:
        return (Path(install_dir).expanduser().resolve() / "DB")

    db_dir = cfg.get("db_dir")
    if db_dir:
        return Path(db_dir).expanduser().resolve()

    env_db = os.environ.get("CMO_DB_DIR")
    if env_db:
        return Path(env_db).expanduser().resolve()

    env_install = os.environ.get("CMO_INSTALL_DIR")
    if env_install:
        return (Path(env_install).expanduser().resolve() / "DB")

    return LOCAL_DB_DIR.resolve()


def config_source_label():
    if CONFIG_FILE.is_file():
        return f"cmo_config.ini ({CONFIG_FILE})"
    if os.environ.get("CMO_DB_DIR") or os.environ.get("CMO_INSTALL_DIR"):
        return "environment variable"
    if LOCAL_DB_DIR.is_dir() and any(LOCAL_DB_DIR.glob("*.db3")):
        return f"local {LOCAL_DB_DIR.name}/ folder"
    return "not configured (see README.md)"


def format_config_setup_hint():
    return (
        f"Configure databases: copy {CONFIG_EXAMPLE.name} to {CONFIG_FILE.name} "
        f"and set cmo_install_dir (preferred) or db_dir to your CMO install. "
        f"Alternatively copy .db3 files into {LOCAL_DB_DIR.name}/."
    )
