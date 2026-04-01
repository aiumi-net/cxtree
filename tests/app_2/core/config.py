"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass
class AppConfig:
    """Central configuration container.

    All values default to safe development-mode settings.
    Production deployments must supply real values via environment variables.
    """

    db_url: str = ""
    secret_key: str = ""
    debug: bool = False
    email_dsn: str = ""
    sms_api_key: str = ""
    redis_url: str = ""
    worker_count: int = 2

    def __post_init__(self) -> None:
        self.db_url = os.getenv("DATABASE_URL", "sqlite:///app2.db")
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.email_dsn = os.getenv("EMAIL_DSN", "")
        self.sms_api_key = os.getenv("SMS_API_KEY", "")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.worker_count = int(os.getenv("WORKER_COUNT", "2"))

    def is_production(self) -> bool:
        """Return True when debug is off and no dev-mode secret is in use."""
        return not self.debug and "dev" not in self.secret_key

    def redis_kwargs(self) -> dict:
        """Parse redis_url into kwargs suitable for the Redis client."""
        return {"url": self.redis_url, "decode_responses": True}
