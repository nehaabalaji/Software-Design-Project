# SQLAlchemy models, mirroring the dict shapes InMemoryStore used to hand
# back directly, so the route modules (auth.py, services.py, ...) don't need
# to change when a SQLStore replaces InMemoryStore.

from datetime import datetime, timezone

from app.extensions import db


class User(db.Model):
    # Required table per the project spec: UserCredentials (User ID, Email,
    # Encrypted password, Role). first_name/last_name are extra profile
    # fields the rest of the app already relies on.
    __tablename__ = "UserCredentials"

    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    first_name = db.Column(db.String(100), nullable=False, default="")
    last_name = db.Column(db.String(100), nullable=False, default="")


class Token(db.Model):
    __tablename__ = "tokens"

    token = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("UserCredentials.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class QueueEntry(db.Model):
    __tablename__ = "queue_entries"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("UserCredentials.id"), nullable=False, index=True)
    service_id = db.Column(db.String(36), db.ForeignKey("services.id"), nullable=False, index=True)
    priority = db.Column(db.String(20), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class HistoryEntry(db.Model):
    __tablename__ = "history_entries"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    user_email = db.Column(db.String(255), nullable=True)
    service_id = db.Column(db.String(36), nullable=True, index=True)
    service_name = db.Column(db.String(100), nullable=True)
    action = db.Column(db.String(20), nullable=False)
    wait_time_minutes = db.Column(db.Integer, nullable=True)
    position_at_join = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), nullable=False, index=True)
    service_id = db.Column(db.String(36), nullable=True)
    service_name = db.Column(db.String(100), nullable=True)
    kind = db.Column(db.String(20), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    read = db.Column(db.Boolean, nullable=False, default=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
