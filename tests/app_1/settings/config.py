"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Central configuration for the application.

    All secrets default to development-safe values.
    Production must supply real values via environment variables.
    """

    secret_key: str = ""
    debug: bool = False
    db_url: str = ""
    allowed_hosts: list[str] = field(default_factory=list)
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        self.secret_key = os.getenv("SECRET_KEY", "dev-secret-do-not-use")  # CX
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.db_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
        raw_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
        self.allowed_hosts = [h.strip() for h in raw_hosts.split(",")]
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

    def is_production(self) -> bool:
        """Return True if running in a production-like environment."""
        return not self.debug and "dev" not in self.secret_key

    def database_engine(self) -> str:
        """Extract the database engine name from the URL."""
        return self.db_url.split("://")[0] if "://" in self.db_url else "unknown"
