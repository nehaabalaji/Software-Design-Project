# History Module - TODO (team)
#
# Track queue participation history for users (in memory is fine).
#
# Suggested endpoints:
#   GET /api/history/mine
#   GET /api/history/          (admin)
#   GET /api/history/stats     (admin)  optional
#
# Usually written to when someone leaves a queue or gets served.

from flask import Blueprint

history_bp = Blueprint("history", __name__)
