"""Settings, read from the environment (and from `.env` in development).

No credential has a default here. A connection string is something a deploy
supplies; baking one in is how a test run ends up writing to production.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Task API"
    debug: bool = False

    # The whole credential lives in the URI: mongodb+srv://user:pass@host/...
    # Keeping it in one value means an Atlas string can be pasted in unchanged.
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "taskapi"
    mongodb_collection: str = "tasks"

    # How long to wait for a server before giving up. Short, so a wrong host
    # fails while someone is still looking at the terminal.
    mongodb_timeout_ms: int = 5000

    @property
    def safe_mongodb_uri(self) -> str:
        """The URI with its password masked, for logs and error messages."""
        parts = urlsplit(self.mongodb_uri)
        if not parts.password:
            return self.mongodb_uri

        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        netloc = f"{parts.username}:***@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


@lru_cache
def get_settings() -> Settings:
    """Cached, so `.env` is read once rather than per request."""
    return Settings()
