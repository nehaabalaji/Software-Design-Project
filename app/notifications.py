# Notification Module - TODO (team)
#
# Trigger notifications when:
#   - a user joins a queue
#   - a user is close to being served
#
# No real email/SMS needed. Logging in memory / returning JSON is fine.
#
# Suggested endpoints:
#   GET  /api/notifications/
#   POST /api/notifications/<id>/read
#   POST /api/notifications/read-all
#
# Can be called from the queue module when join/serve/almost-ready happens.

from flask import Blueprint

notifications_bp = Blueprint("notifications", __name__)
