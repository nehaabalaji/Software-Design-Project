#!/usr/bin/env bash
# One-time local setup for QueueSmart (Mac / Linux).
# Creates a virtual environment and installs Python dependencies.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed. Install Python 3, then run this again."
  exit 1
fi

echo "Creating virtual environment in .venv ..."
python3 -m venv .venv

echo "Installing dependencies from requirements.txt ..."
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo
echo "Setup complete."
echo "Next steps:"
echo "  1. Activate the environment:  source .venv/bin/activate"
echo "  2. Start the API:             python run.py"
echo "  3. Run tests (optional):      pytest -v"
echo
echo "API will be at http://127.0.0.1:5000"
echo "Open the HTML files in a browser for the frontend (login.html, etc.)."
echo
echo "Note: .venv is local to your machine and is not committed to GitHub."
