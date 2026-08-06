import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REQ = _ROOT / "requirements.txt"


_REQUIRED_MODULES = ["flask", "flask_sqlalchemy", "flask_migrate", "pymysql", "dotenv"]


def ensure():
    if all(importlib.util.find_spec(mod) is not None for mod in _REQUIRED_MODULES):
        return
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(_REQ)],
        cwd=str(_ROOT),
    )
    os.execv(sys.executable, [sys.executable, *sys.argv])
