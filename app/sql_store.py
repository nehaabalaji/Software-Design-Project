# MySQL-backed store. Same method signatures and return shapes as
# InMemoryStore (app/store.py) so auth.py/services.py/queues.py/etc. don't
# need to change -- only app/__init__.py picks which store to hand them.

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import HistoryEntry, Notification, QueueEntry, Service, Token, User

_PRIORITY_WEIGHT = {"low": 0, "medium": 1, "high": 2, "urgent": 3}


def _iso(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


class SQLStore:
    def create_user(self, *, email, password_hash, role, first_name="", last_name=""):
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            raise ValueError("Email is already registered")

        user = User(
            id=str(uuid4()),
            email=email,
            password_hash=password_hash,
            role=role,
            first_name=(first_name or "").strip(),
            last_name=(last_name or "").strip(),
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValueError("Email is already registered")
        return self._public_user(user)

    def get_user_by_email(self, email):
        user = User.query.filter_by(email=email.strip().lower()).first()
        return self._user_dict(user) if user else None

    def get_user_by_id(self, user_id):
        user = db.session.get(User, user_id)
        return self._user_dict(user) if user else None

    def create_token(self, user_id):
        token = str(uuid4())
        db.session.add(Token(token=token, user_id=user_id))
        db.session.commit()
        return token

    def get_user_id_for_token(self, token):
        row = db.session.get(Token, token)
        return row.user_id if row else None

    def revoke_token(self, token):
        row = db.session.get(Token, token)
        if not row:
            return False
        db.session.delete(row)
        db.session.commit()
        return True

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def add_notification(self, *, user_id, service_id=None, kind, message):
        service = db.session.get(Service, service_id) if service_id else None
        notification = Notification(
            id=str(uuid4()),
            user_id=user_id,
            service_id=service_id,
            service_name=service.name if service else None,
            kind=kind,
            message=message,
            read=False,
        )
        db.session.add(notification)
        db.session.commit()
        return self._notification_dict(notification)

    def list_notifications(self, user_id):
        rows = Notification.query.filter_by(user_id=user_id).all()
        return [self._notification_dict(n) for n in rows]

    def get_notification(self, notification_id):
        row = db.session.get(Notification, notification_id)
        return self._notification_dict(row) if row else None

    def mark_notification_read(self, notification_id, user_id):
        row = db.session.get(Notification, notification_id)
        if row is None or row.user_id != user_id:
            return None
        row.read = True
        db.session.commit()
        return self._notification_dict(row)

    def mark_all_notifications_read(self, user_id):
        rows = Notification.query.filter_by(user_id=user_id, read=False).all()
        for row in rows:
            row.read = True
        db.session.commit()
        return len(rows)

    def clear(self):
        Notification.query.delete()
        HistoryEntry.query.delete()
        QueueEntry.query.delete()
        Token.query.delete()
        Service.query.delete()
        User.query.delete()
        db.session.commit()

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def create_service(self, *, name, description, duration, priority):
        service = Service(
            id=str(uuid4()), name=name, description=description,
            duration=duration, priority=priority,
        )
        db.session.add(service)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ValueError("A service with this name already exists")
        return self._service_dict(service)

    def list_services(self):
        return [self._service_dict(s) for s in Service.query.all()]

    def get_service(self, service_id):
        service = db.session.get(Service, service_id)
        return self._service_dict(service) if service else None

    def service_name_exists(self, name, exclude_id=None):
        target = name.strip().lower()
        query = Service.query.filter(db.func.lower(Service.name) == target)
        if exclude_id:
            query = query.filter(Service.id != exclude_id)
        return query.first() is not None

    def update_service(self, service_id, **fields):
        service = db.session.get(Service, service_id)
        if not service:
            return None
        for key, value in fields.items():
            setattr(service, key, value)
        service.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return self._service_dict(service)

    def delete_service(self, service_id):
        service = db.session.get(Service, service_id)
        if not service:
            return False
        db.session.delete(service)
        db.session.commit()
        return True

    def get_queue_length(self, service_id):
        return QueueEntry.query.filter_by(service_id=service_id).count()

    # ------------------------------------------------------------------
    # Queue entries
    # ------------------------------------------------------------------

    def join_queue(self, *, user_id, service_id):
        service = db.session.get(Service, service_id)
        if not service:
            raise ValueError("Service not found")

        if QueueEntry.query.filter_by(user_id=user_id, service_id=service_id).first():
            raise ValueError("Already in this queue")

        entry = QueueEntry(
            id=str(uuid4()), user_id=user_id, service_id=service_id, priority=service.priority,
        )
        db.session.add(entry)
        db.session.commit()
        position = self._position(service_id, entry.id)
        return self._queue_entry_dict(entry), position

    def leave_queue(self, *, user_id, service_id):
        entry = QueueEntry.query.filter_by(user_id=user_id, service_id=service_id).first()
        if not entry:
            return None
        entry_dict = self._queue_entry_dict(entry)
        db.session.delete(entry)
        db.session.commit()
        return entry_dict

    def list_queue(self, service_id):
        return [self._queue_entry_dict(e) for e in self._sorted_entries(service_id)]

    def get_queue_position(self, *, user_id, service_id):
        entries = self._sorted_entries(service_id)
        for i, entry in enumerate(entries):
            if entry.user_id == user_id:
                return i + 1, self._queue_entry_dict(entry)
        return None, None

    def list_queue_entries_for_user(self, user_id):
        entries = QueueEntry.query.filter_by(user_id=user_id).all()
        results = []
        for entry in entries:
            service = db.session.get(Service, entry.service_id)
            duration = service.duration if service else 0
            ordered = self._sorted_entries(entry.service_id)
            position = next((i + 1 for i, e in enumerate(ordered) if e.id == entry.id), None)

            entry_dict = self._queue_entry_dict(entry)
            entry_dict["service_name"] = service.name if service else None
            entry_dict["position"] = position
            entry_dict["estimated_wait_minutes"] = (position * duration) if position else None
            results.append(entry_dict)
        return results

    def serve_next(self, service_id):
        ordered = self._sorted_entries(service_id)
        if not ordered:
            return None
        entry = ordered[0]
        entry_dict = self._queue_entry_dict(entry)
        entry_dict["status"] = "served"
        db.session.delete(entry)
        db.session.commit()
        return entry_dict

    def _sorted_entries(self, service_id):
        entries = QueueEntry.query.filter_by(service_id=service_id).all()
        return sorted(
            entries,
            key=lambda e: (-_PRIORITY_WEIGHT.get(e.priority, 0), e.joined_at),
        )

    def _position(self, service_id, entry_id):
        for i, entry in enumerate(self._sorted_entries(service_id)):
            if entry.id == entry_id:
                return i + 1
        return None

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def add_history_entry(self, *, user_id, service_id, action,
                           wait_time_minutes=None, position_at_join=None, notes=None):
        user = db.session.get(User, user_id)
        service = db.session.get(Service, service_id) if service_id else None
        entry = HistoryEntry(
            id=str(uuid4()),
            user_id=user_id,
            user_email=user.email if user else None,
            service_id=service_id,
            service_name=service.name if service else None,
            action=action,
            wait_time_minutes=wait_time_minutes,
            position_at_join=position_at_join,
            notes=notes,
        )
        db.session.add(entry)
        db.session.commit()
        return self._history_dict(entry)

    def list_history(self):
        return [self._history_dict(e) for e in HistoryEntry.query.all()]

    # ------------------------------------------------------------------
    # dict builders -- match the shapes InMemoryStore used to return
    # ------------------------------------------------------------------

    @staticmethod
    def _public_user(user):
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }

    @staticmethod
    def _user_dict(user):
        return {
            "id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }

    @staticmethod
    def _service_dict(service):
        return {
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "duration": service.duration,
            "priority": service.priority,
            "created_at": _iso(service.created_at),
            "updated_at": _iso(service.updated_at),
        }

    @staticmethod
    def _queue_entry_dict(entry):
        return {
            "id": entry.id,
            "user_id": entry.user_id,
            "service_id": entry.service_id,
            "priority": entry.priority,
            "status": "waiting",
            "joined_at": _iso(entry.joined_at),
        }

    @staticmethod
    def _history_dict(entry):
        return {
            "id": entry.id,
            "user_id": entry.user_id,
            "user_email": entry.user_email,
            "service_id": entry.service_id,
            "service_name": entry.service_name,
            "action": entry.action,
            "wait_time_minutes": entry.wait_time_minutes,
            "position_at_join": entry.position_at_join,
            "notes": entry.notes,
            "timestamp": _iso(entry.timestamp),
        }

    @staticmethod
    def _notification_dict(notification):
        return {
            "id": notification.id,
            "user_id": notification.user_id,
            "service_id": notification.service_id,
            "service_name": notification.service_name,
            "kind": notification.kind,
            "message": notification.message,
            "read": notification.read,
            "timestamp": _iso(notification.timestamp),
        }
