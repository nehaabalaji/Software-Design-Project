# Database configuration.
# Tries MySQL first (team / production setup). If MySQL isn't running,
# falls back to a local SQLite file so the website still works on this machine.

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_USER = os.environ.get("DB_USER", "queuesmart")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "queuesmart_dev_pw")
DB_NAME = os.environ.get("DB_NAME", "queuesmart_dev")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SQLITE_PATH = _PROJECT_ROOT / "queuesmart.db"
_FORCE_SQLITE = os.environ.get("USE_SQLITE", "").lower() in {"1", "true", "yes"}

_MYSQL_URI = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)
_SQLITE_URI = f"sqlite:///{_SQLITE_PATH}"


def _mysql_reachable():
    try:
        import pymysql

        conn = pymysql.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False


if _FORCE_SQLITE or not _mysql_reachable():
    SQLALCHEMY_DATABASE_URI = _SQLITE_URI
    USING_SQLITE = True
else:
    SQLALCHEMY_DATABASE_URI = _MYSQL_URI
    USING_SQLITE = False
