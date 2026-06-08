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


def resolve_aeroapi_key(explicit=None):
    """
    FlightAware AeroAPI key for the x-apikey header.

    Priority: explicit argument > AEROAPI_API_KEY env > cmo_config.ini [aeroapi] api_key.
    Returns None when no key is configured (callers should skip AeroAPI features).
    """
    if explicit:
        return explicit.strip()

    env_key = os.environ.get("AEROAPI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    if not CONFIG_FILE.is_file():
        return None
    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE, encoding="utf-8")
    if "aeroapi" not in parser:
        return None
    key = parser["aeroapi"].get("api_key", "").strip()
    # Treat the documented placeholder as "not configured".
    if not key or key.upper() == "YOUR_AEROAPI_KEY_HERE":
        return None
    return key


def aeroapi_config():
    """Return the raw ``[aeroapi]`` section as a dict (empty if absent)."""
    if not CONFIG_FILE.is_file():
        return {}
    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE, encoding="utf-8")
    if "aeroapi" not in parser:
        return {}
    return dict(parser["aeroapi"])


def resolve_aeroapi_verify_ssl(explicit=None):
    """TLS verification toggle. Default True; honor env + config opt-out.

    Useful behind corporate TLS interception (self-signed CA in chain).
    Prefer setting ``ca_bundle`` over disabling verification.
    """
    if explicit is not None:
        return bool(explicit)
    env = os.environ.get("AEROAPI_VERIFY_SSL")
    if env is not None:
        return env.strip().lower() not in ("0", "false", "no", "off")
    cfg = aeroapi_config().get("verify_ssl")
    if cfg is not None:
        return cfg.strip().lower() not in ("0", "false", "no", "off")
    return True


def resolve_aeroapi_ca_bundle(explicit=None):
    """Path to a CA bundle (PEM) for TLS verification, or None."""
    if explicit:
        return explicit
    env = os.environ.get("AEROAPI_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if env:
        return env
    cfg = aeroapi_config().get("ca_bundle")
    return cfg or None


def aeroapi_key_source_label():
    if os.environ.get("AEROAPI_API_KEY"):
        return "AEROAPI_API_KEY environment variable"
    if CONFIG_FILE.is_file():
        return f"cmo_config.ini [aeroapi] ({CONFIG_FILE})"
    return "not configured"


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
