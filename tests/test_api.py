"""End-to-end tests over the six endpoints, against a throwaway database."""

import importlib
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    # A temp file per test, so tests never see each other's rows and the real
    # tasks.db is never touched.
    tmp = Path(tempfile.mkdtemp()) / "test.db"

    from app import database
    monkeypatch.setattr(database, "DB_PATH", tmp)

    from app import main
    importlib.reload(main)

    with TestClient(main.app) as c:
        yield c

    os.unlink(tmp)


def make(client, **over):
    body = {"title": "Write the docs", "description": "d", "priority": "high"} | over
    r = client.post("/tasks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_returns_201_and_defaults(client):
    task = make(client)
    assert task["id"] > 0
    assert task["title"] == "Write the docs"
    assert task["status"] == "todo"          # the default, not sent
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
    r = client.get("/tasks/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "No task with id 999"


def test_put_replaces_every_field(client):
    task = make(client)
    r = client.put(
        f"/tasks/{task['id']}",
        json={"title": "new", "description": "", "status": "done", "priority": "low"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "new"
    assert r.json()["priority"] == "low"


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
