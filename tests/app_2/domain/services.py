"""Application-level domain services."""

from domain.models import Notification, User
from domain.notifications.email_ import EmailDispatcher
from domain.notifications.sms_ import SmsDispatcher


class UserService:
    """CRUD service for User entities backed by an in-memory store."""

    def __init__(self, db_url: str) -> None:
        self._db_url = db_url
        self._store: dict[int, User] = {}
        self._counter = 0

    def next_id(self) -> int:
        self._counter += 1
        return self._counter

    def save(self, user: User) -> None:
        """Persist (insert or update) a user."""
        self._store[user.id] = user

    def get(self, user_id: int) -> User | None:
        """Return user by id or None."""
        return self._store.get(user_id)

    def list_all(self) -> list[User]:
        """Return all stored users."""
        return list(self._store.values())

    def delete(self, user_id: int) -> bool:
        """Remove a user. Returns True if the user existed."""
        if user_id in self._store:
            del self._store[user_id]
            return True
        return False


class NotificationService:
    """Fan-out service that dispatches notifications over email and SMS."""

    def __init__(self, email_dsn: str, sms_api_key: str) -> None:
        self._email = EmailDispatcher(email_dsn)
        self._sms = SmsDispatcher(sms_api_key)

    def send(self, notification: Notification) -> bool:
        """Dispatch a notification over the appropriate channel.

        Returns True if the notification was sent successfully.
        """
        if notification.channel == "sms":
            ok = self._sms.dispatch(notification)
        else:
            ok = self._email.dispatch(notification)
        if ok:
            notification.mark_sent()
        return ok

    def broadcast(self, notifications: list[Notification]) -> int:
        """Send all notifications. Returns count of successful dispatches."""
        return sum(1 for n in notifications if self.send(n))
