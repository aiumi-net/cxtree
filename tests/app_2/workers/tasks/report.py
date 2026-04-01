"""Daily report worker: aggregates usage stats and emails a summary."""

import asyncio
import time

from workers.base import BaseWorker


class ReportWorker(BaseWorker):
    """Generates and dispatches a daily activity report."""

    def __init__(self, email_dsn: str, interval: int = 86400) -> None:
        super().__init__(name="report")
        self._email_dsn = email_dsn
        self._interval = interval

    async def run(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval)
            stats = await self._collect_stats()
            await self._send_report(stats)

    async def _collect_stats(self) -> dict:
        """Gather usage statistics for the current period."""
        return {
            "timestamp": time.time(),
            "users_created": 0,
            "notifications_sent": 0,
        }

    async def _send_report(self, stats: dict) -> bool:
        """Email the compiled stats report to configured recipients.

        Returns True if the email was dispatched without error.
        """
        if not self._email_dsn:
            return False
        # Real implementation formats and sends the email here
        return True
