# Queue Management + Wait-Time Estimation - TODO (team)
#
# Users should be able to:
#   - join a queue
#   - leave a queue
#
# Administrators should be able to:
#   - view the current queue
#   - serve the next user
#
# Ordering should use arrival order and priority when applicable.
# Wait time can be simple: position * expected duration.
#
# Suggested endpoints:
#   POST /api/queues/join
#   POST /api/queues/leave
#   GET  /api/queues/mine
#   GET  /api/queues/service/<service_id>
#   POST /api/queues/serve-next   (admin)
#
# Use login_required / admin_required from app.utils
# Auth already gives you the current user + role.

from flask import Blueprint

queues_bp = Blueprint("queues", __name__)
