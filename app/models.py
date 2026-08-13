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
    """Service offered by the organization.

    Column mapping to the assignment spec:
      id            → service_id (UUID string PK; consistent with other FKs)
      name          → name (NOT NULL, non-empty)
      description   → description (TEXT)
      duration      → expected_duration (INT, must be > 0)
      priority      → human-readable level (low/medium/high/urgent)
      priority_level→ INT DEFAULT 0 (numeric form of priority)
      created_at    → created_at
    """

    __tablename__ = "services"
    __table_args__ = (
        db.CheckConstraint("CHAR_LENGTH(TRIM(name)) > 0", name="chk_services_name_not_empty"),
        db.CheckConstraint("duration > 0", name="chk_services_duration_positive"),
    )

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Integer, nullable=False)  # expected_duration (minutes)
    priority = db.Column(db.String(20), nullable=False)
    priority_level = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    managed_queue = db.relationship(
        "Queue",
        back_populates="service",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Queue(db.Model):
    """Managed queue for a service (open / closed).

    Assignment columns:
      queue_id, service_id (FK CASCADE), status ENUM('open','closed'), created_at
    """

    __tablename__ = "queues"

    queue_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    service_id = db.Column(
        db.String(36),
        db.ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status = db.Column(db.Enum("open", "closed", name="queue_status"), nullable=False, default="open")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    service = db.relationship("Service", back_populates="managed_queue")


class QueueEntry(db.Model):
    """Person waiting in a service's queue.

    Assignment columns: Queue ID (service_id -- each service has exactly one
    managed Queue), User ID, Position, Join time, Status.
    Entries are kept (not deleted) after leaving/being served so the row
    itself carries a status history, not just the separate HistoryEntry log.
    """

    __tablename__ = "queue_entries"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("UserCredentials.id"), nullable=False, index=True)
    service_id = db.Column(db.String(36), db.ForeignKey("services.id"), nullable=False, index=True)
    priority = db.Column(db.String(20), nullable=False)
    status = db.Column(
        db.Enum("waiting", "served", "canceled", name="queue_entry_status"),
        nullable=False,
        default="waiting",
    )
    position = db.Column(db.Integer, nullable=True)
    joined_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    served_at = db.Column(db.DateTime, nullable=True)


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

class UserProfile(db.Model):
    __tablename__ = "user_profiles"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("UserCredentials.id"), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False, default="")
    phone = db.Column(db.String(30), nullable=True)
    preferences = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
