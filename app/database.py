"""MongoDB connection handling.

One client for the process, not one per request: PyMongo's client owns a
connection pool and is thread-safe, so making a new one per request would build
and tear down pools continuously.
"""

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection

from .config import get_settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = MongoClient(
            s.mongodb_uri,
            serverSelectionTimeoutMS=s.mongodb_timeout_ms,
            # BSON dates carry no zone, so without this reads come back naive
            # while writes are UTC-aware — the same field serialising two ways
            # depending on whether the client had just written it.
            tz_aware=True,
        )
    return _client


def get_collection() -> Collection:
    s = get_settings()
    return get_client()[s.mongodb_db][s.mongodb_collection]


def init_db() -> None:
    """Create the indexes the queries rely on.

    Both are idempotent, so this is safe to run on every start. Without the
    compound index the default listing — filter by status, sort by newest —
    is a collection scan followed by an in-memory sort.
    """
    col = get_collection()
    col.create_index([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created")
    col.create_index([("created_at", DESCENDING)], name="created_desc")


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
