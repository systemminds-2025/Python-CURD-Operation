"""End-to-end tests over the six endpoints, against a throwaway database.

Each test gets its own MongoDB database, dropped afterwards, so tests never see
each other's documents and the configured database is never touched.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

# Local by default, deliberately. Tests create and drop a database per test,
# which is not something to point at a shared cluster. Override only on
# purpose, with TEST_MONGODB_URI.
URI = os.environ.get("TEST_MONGODB_URI", "mongodb://localhost:27017")


@pytest.fixture()
def client(monkeypatch):
    db_name = f"taskapi_test_{uuid.uuid4().hex[:8]}"

    monkeypatch.setenv("MONGODB_URI", URI)
    monkeypatch.setenv("MONGODB_DB", db_name)

    from app import config, database

    # Settings are cached for the process, and the client is a module global;
    # both have to be dropped or the test would talk to the real database.
    config.get_settings.cache_clear()
    database.close_client()

    from app.main import app

    try:
        with TestClient(app) as c:
            yield c
    except PyMongoError as e:
        pytest.skip(f"MongoDB not reachable at {URI}: {e}")
    finally:
        try:
            database.get_client().drop_database(db_name)
        except PyMongoError:
            pass
        database.close_client()
        config.get_settings.cache_clear()


def make(client, **over):
    body = {"title": "Write the docs", "description": "d", "priority": "high"} | over
    r = client.post("/tasks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_returns_201_and_defaults(client):
    task = make(client)
    assert len(task["id"]) == 24                 # an ObjectId, as a string
    assert task["title"] == "Write the docs"
    assert task["status"] == "todo"              # the default, not sent
    assert task["created_at"] == task["updated_at"]


def test_create_rejects_empty_title(client):
    assert client.post("/tasks", json={"title": ""}).status_code == 422


def test_list_filters_and_pages(client):
    make(client, title="a")
    make(client, title="b", status="done")

    assert len(client.get("/tasks").json()) == 2
    done = client.get("/tasks", params={"status": "done"}).json()
    assert [t["title"] for t in done] == ["b"]
    assert len(client.get("/tasks", params={"limit": 1}).json()) == 1


def test_get_by_id(client):
    task = make(client)
    assert client.get(f"/tasks/{task['id']}").json()["id"] == task["id"]


def test_get_missing_is_404(client):
    missing = "0" * 24
    r = client.get(f"/tasks/{missing}")
    assert r.status_code == 404
    assert r.json()["detail"] == f"No task with id {missing}"


def test_malformed_id_is_404_not_500(client):
    # "abc" is not an ObjectId. That has to be a miss, not a crash.
    assert client.get("/tasks/abc").status_code == 404
    assert client.delete("/tasks/abc").status_code == 404


def test_put_replaces_every_field(client):
    task = make(client)
    r = client.put(
        f"/tasks/{task['id']}",
        json={"title": "new", "description": "", "status": "done", "priority": "low"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "new"
    assert r.json()["priority"] == "low"
    assert r.json()["created_at"] == task["created_at"]   # replacement, not re-creation


def test_put_requires_all_fields(client):
    task = make(client)
    assert client.put(f"/tasks/{task['id']}", json={"title": "only"}).status_code == 422


def test_patch_leaves_omitted_fields_alone(client):
    task = make(client)
    r = client.patch(f"/tasks/{task['id']}", json={"status": "in_progress"})
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert r.json()["title"] == task["title"]        # untouched
    assert r.json()["priority"] == "high"            # untouched


def test_patch_with_no_fields_is_a_noop(client):
    task = make(client)
    r = client.patch(f"/tasks/{task['id']}", json={})
    assert r.status_code == 200
    assert r.json()["title"] == task["title"]


def test_delete_then_gone(client):
    task = make(client)
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    assert client.get(f"/tasks/{task['id']}").status_code == 404
    assert client.delete(f"/tasks/{task['id']}").status_code == 404


def test_delete_all_removes_every_task(client):
    make(client, title="a")
    make(client, title="b")

    r = client.delete("/tasks")
    assert r.status_code == 200
    assert r.json() == {"deleted": 2}
    assert client.get("/tasks").json() == []


def test_health_reports_the_database(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
