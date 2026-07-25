import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REQ = _ROOT / "requirements.txt"


def ensure():
    if importlib.util.find_spec("flask") is not None:
        return
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(_REQ)],
        cwd=str(_ROOT),
    )
    os.execv(sys.executable, [sys.executable, *sys.argv])
