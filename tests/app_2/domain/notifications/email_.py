"""Email notification dispatcher."""

from domain.models import Notification


class EmailDispatcher:
    """Send notifications via SMTP.

    Uses a simple connection-per-message strategy suitable for low-volume apps.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def dispatch(self, notification: Notification) -> bool:
        """Send a single email notification.

        Returns True on success, False if the DSN is unconfigured.
        """
        if not self._dsn:
            return False
        # Real implementation would open SMTP connection here
        return True

    def dispatch_bulk(self, notifications: list[Notification]) -> list[bool]:
        """Send multiple emails and return per-notification success flags."""
        return [self.dispatch(n) for n in notifications]
