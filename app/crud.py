"""Data access. Every function returns plain dicts shaped for the response."""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING
from pymongo.collection import Collection
from pymongo.collection import ReturnDocument

FIELDS = ("title", "description", "status", "priority")


def _now() -> datetime:
    """Now, at the precision MongoDB actually stores.

    BSON dates hold milliseconds. Generating microseconds meant the document
    returned by a create carried three digits that the stored document did not,
    so re-reading the same task gave a different created_at.
    """
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _out(doc: dict | None) -> dict | None:
    """Mongo's `_id` becomes the API's `id`, as a string."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


def to_object_id(task_id: str) -> ObjectId | None:
    """None for anything that is not a valid id.

    A malformed id is a miss, not a crash — the caller turns it into the same
    404 as an id that is well-formed but absent.
    """
    try:
        return ObjectId(task_id)
    except (InvalidId, TypeError):
        return None


def create(col: Collection, data: dict) -> dict:
    now = _now()
    doc = {**{f: data[f] for f in FIELDS}, "created_at": now, "updated_at": now}
    res = col.insert_one(doc)
    return _out({**doc, "_id": res.inserted_id})


def list_all(
    col: Collection,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = {"status": status} if status else {}
    cursor = col.find(query).sort("created_at", DESCENDING).skip(offset).limit(limit)
    return [_out(d) for d in cursor]


def get(col: Collection, task_id: str) -> dict | None:
    oid = to_object_id(task_id)
    return _out(col.find_one({"_id": oid})) if oid else None


def replace(col: Collection, task_id: str, data: dict) -> dict | None:
    oid = to_object_id(task_id)
    if oid is None:
        return None

    # $set rather than replace_one, so created_at survives a replacement — the
    # resource is the same one, and when it was created has not changed.
    return _out(
        col.find_one_and_update(
            {"_id": oid},
            {"$set": {**{f: data[f] for f in FIELDS}, "updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
    )


def patch(col: Collection, task_id: str, changes: dict) -> dict | None:
    oid = to_object_id(task_id)
    if oid is None:
        return None

    # Only known fields are ever written, so a stray key in the body cannot
    # add an arbitrary attribute to the document.
    updates = {f: changes[f] for f in FIELDS if f in changes}
    if not updates:
        return _out(col.find_one({"_id": oid}))  # nothing sent is a no-op, not an error

    return _out(
        col.find_one_and_update(
            {"_id": oid},
            {"$set": {**updates, "updated_at": _now()}},
            return_document=ReturnDocument.AFTER,
        )
    )


def delete(col: Collection, task_id: str) -> bool:
    oid = to_object_id(task_id)
    if oid is None:
        return False
    return col.delete_one({"_id": oid}).deleted_count > 0
