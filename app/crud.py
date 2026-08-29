"""Data access. Every function returns plain dicts, not response models."""

import sqlite3
from datetime import datetime, timezone

FIELDS = ("title", "description", "status", "priority")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create(conn: sqlite3.Connection, data: dict) -> dict:
    now = _now()
    cur = conn.execute(
        """INSERT INTO tasks (title, description, status, priority, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["title"], data["description"], data["status"], data["priority"], now, now),
    )
    return get(conn, cur.lastrowid)


def list_all(
    conn: sqlite3.Connection,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    # Built as a parameterised query rather than interpolated, so a status can
    # never carry SQL into the statement.
    sql = "SELECT * FROM tasks"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get(conn: sqlite3.Connection, task_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def replace(conn: sqlite3.Connection, task_id: int, data: dict) -> dict | None:
    if get(conn, task_id) is None:
        return None
    conn.execute(
        """UPDATE tasks
              SET title = ?, description = ?, status = ?, priority = ?, updated_at = ?
            WHERE id = ?""",
        (data["title"], data["description"], data["status"], data["priority"], _now(), task_id),
    )
    return get(conn, task_id)


def patch(conn: sqlite3.Connection, task_id: int, changes: dict) -> dict | None:
    if get(conn, task_id) is None:
        return None
    if not changes:
        return get(conn, task_id)  # nothing sent is not an error, just a no-op

    # Only known columns are ever named, so a stray key cannot reach the SQL.
    sets = [f"{f} = ?" for f in FIELDS if f in changes]
    values = [changes[f] for f in FIELDS if f in changes]
    conn.execute(
        f"UPDATE tasks SET {', '.join(sets)}, updated_at = ? WHERE id = ?",
        [*values, _now(), task_id],
    )
    return get(conn, task_id)


def delete(conn: sqlite3.Connection, task_id: int) -> bool:
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cur.rowcount > 0
