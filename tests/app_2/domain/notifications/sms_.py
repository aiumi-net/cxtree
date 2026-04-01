"""SMS notification dispatcher."""

from domain.models import Notification


class SmsDispatcher:
    """Send notifications via a third-party SMS API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def dispatch(self, notification: Notification) -> bool:
        """Send an SMS to the recipient phone number derived from user_id.

        Returns True on success, False if the API key is unconfigured.
        """
        if not self._api_key:
            return False
        # Real implementation calls SMS provider API here
        return True
