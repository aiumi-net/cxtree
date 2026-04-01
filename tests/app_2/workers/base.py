"""Background worker infrastructure."""

import asyncio
from abc import ABC, abstractmethod


class BaseWorker(ABC):
    """Abstract base for all background workers.

    Subclasses implement run() and are managed by WorkerPool.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._running = False

    @abstractmethod
    async def run(self) -> None:
        """Execute the worker's main loop. Called by WorkerPool.start()."""

    async def start(self) -> None:
        """Start the worker loop. Sets _running flag."""
        self._running = True
        await self.run()

    def stop(self) -> None:
        """Signal the worker to stop at its next iteration."""
        self._running = False


class WorkerPool:
    """Manages a set of BaseWorker instances, starting them concurrently."""

    def __init__(self, max_workers: int = 4) -> None:
        self._workers: list[BaseWorker] = []
        self._max = max_workers

    def register(self, worker: BaseWorker) -> None:
        """Add a worker to the pool. Raises if pool is already at capacity."""
        if len(self._workers) >= self._max:
            raise RuntimeError(f"Pool full ({self._max} workers max)")
        self._workers.append(worker)

    async def start(self) -> None:
        """Start all registered workers concurrently."""
        await asyncio.gather(*(w.start() for w in self._workers))

    def stop_all(self) -> None:
        """Signal every worker to stop."""
        for w in self._workers:
            w.stop()
