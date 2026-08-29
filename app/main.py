"""A small CRUD API over a single `tasks` resource, stored in MongoDB.

Six endpoints:

    POST   /tasks       create
    GET    /tasks       list, filterable and paged
    GET    /tasks/{id}  read one
    PUT    /tasks/{id}  replace
    PATCH  /tasks/{id}  edit some fields
    DELETE /tasks/{id}  remove

Configuration — the connection string included — comes from `.env`.
Run it with:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status as http
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from . import crud
from .config import Settings, get_settings
from .database import close_client, get_collection, init_db
from .models import Status, Task, TaskCreate, TaskPatch, TaskReplace


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Indexes are created once at startup rather than per request. A database
    # that cannot be reached should not stop the process — /health is then the
    # thing that says so, which is more use than a crash loop.
    try:
        init_db()
    except PyMongoError as e:
        print(f"[startup] MongoDB not ready: {e}")
    yield
    close_client()


app = FastAPI(
    title="Task API",
    description="A small CRUD API over a single tasks resource, stored in MongoDB.",
    version="2.0.0",
    lifespan=lifespan,
)


def collection() -> Collection:
    return get_collection()


def _found(task: dict | None, task_id: str) -> dict:
    """Every by-id route needs the same 404, worded the same way."""
    if task is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"No task with id {task_id}")
    return task


@app.get("/health", tags=["meta"])
def health(settings: Settings = Depends(get_settings)) -> dict:
    """Liveness, plus whether the database is actually reachable.

    The URI is reported with its password masked — useful for spotting a wrong
    host, and not a way to read the credential out of a running service.
    """
    try:
        get_collection().database.client.admin.command("ping")
        db = "ok"
    except PyMongoError as e:
        db = f"unreachable: {type(e).__name__}"

    return {"status": "ok", "database": db, "uri": settings.safe_mongodb_uri}


@app.post("/tasks", response_model=Task, status_code=http.HTTP_201_CREATED, tags=["tasks"])
def create_task(payload: TaskCreate, col: Collection = Depends(collection)) -> dict:
    """Create a task. Responds 201 with the stored document, id and timestamps included."""
    return crud.create(col, payload.model_dump(mode="json"))


@app.get("/tasks", response_model=list[Task], tags=["tasks"])
def list_tasks(
    status: Status | None = Query(default=None, description="Only tasks in this status."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    col: Collection = Depends(collection),
) -> list[dict]:
    """List tasks, newest first. Paged so the response cannot grow unbounded."""
    return crud.list_all(col, status.value if status else None, limit, offset)


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def get_task(task_id: str, col: Collection = Depends(collection)) -> dict:
    return _found(crud.get(col, task_id), task_id)


@app.put("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def replace_task(task_id: str, payload: TaskReplace, col: Collection = Depends(collection)) -> dict:
    """Replace every field. A missing field is a 422, not a silent keep."""
    return _found(crud.replace(col, task_id, payload.model_dump(mode="json")), task_id)


@app.patch("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def edit_task(task_id: str, payload: TaskPatch, col: Collection = Depends(collection)) -> dict:
    """Edit some fields. `exclude_unset` is what keeps an omitted field from
    being written as null — sending nothing means "leave it alone"."""
    changes = payload.model_dump(mode="json", exclude_unset=True)
    return _found(crud.patch(col, task_id, changes), task_id)


@app.delete("/tasks/{task_id}", status_code=http.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(task_id: str, col: Collection = Depends(collection)) -> None:
    if not crud.delete(col, task_id):
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"No task with id {task_id}")
