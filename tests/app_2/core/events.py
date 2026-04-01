"""Application lifecycle events: startup and shutdown hooks."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from core.config import AppConfig

_startup_hooks: list = []
_shutdown_hooks: list = []


def on_startup(fn) -> None:
    """Register a coroutine function to run on application startup."""
    _startup_hooks.append(fn)


def on_shutdown(fn) -> None:
    """Register a coroutine function to run on application shutdown."""
    _shutdown_hooks.append(fn)


@asynccontextmanager
async def lifespan(config: AppConfig) -> AsyncIterator[None]:
    """Async context manager that fires startup then shutdown hooks."""
    for hook in _startup_hooks:
        await hook(config)
    try:
        yield
    finally:
        for hook in reversed(_shutdown_hooks):
            await hook(config)


async def _default_startup(config: AppConfig) -> None:
    if config.debug:
        print("[startup] debug mode enabled")  # ---
        print("[startup] db:", config.db_url)  # ---


on_startup(_default_startup)
