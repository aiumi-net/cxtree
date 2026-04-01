"""Periodic cleanup worker: removes expired sessions and soft-deleted users."""

import asyncio
import time

from workers.base import BaseWorker


class CleanupWorker(BaseWorker):
    """Runs every *interval* seconds and purges stale data."""

    def __init__(self, interval: int = 300) -> None:
        super().__init__(name="cleanup")
        self._interval = interval
        self._last_run: float = 0.0

    async def run(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval)
            self._last_run = time.time()
            await self._purge_sessions()
            await self._purge_users()

    async def _purge_sessions(self) -> int:
        """Delete all expired sessions from the store. Returns count removed."""
        # Placeholder: real impl queries the session repository
        return 0

    async def _purge_users(self) -> int:
        """Hard-delete users that have been soft-deleted for >30 days."""
        return 0
