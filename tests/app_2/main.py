"""Entry point for app_2. Bootstraps the application and starts workers.

Wires together the API, domain services, and background workers.
"""

from api.routes import create_router
from core.config import AppConfig
from core.events import lifespan
from domain.services import NotificationService, UserService
from workers.base import WorkerPool


def build_app(config: AppConfig) -> dict:
    """Construct and return the fully wired application context."""
    user_svc = UserService(config.db_url)  # ++
    notif_svc = NotificationService(
        email_dsn=config.email_dsn,
        sms_api_key=config.sms_api_key,
    )
    router = create_router(user_svc, notif_svc)
    pool = WorkerPool(max_workers=config.worker_count)
    return {
        "router": router,
        "user_svc": user_svc,
        "notif_svc": notif_svc,
        "pool": pool,
    }


async def main() -> None:
    config = AppConfig()
    async with lifespan(config):
        app = build_app(config)
        await app["pool"].start()
        print("App running")  # ---
        print("Config:", config)  # ---
        print("Router:", app["router"])  # ---


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
