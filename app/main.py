"""A small CRUD API over a single `tasks` resource.

Six endpoints:

    POST   /tasks       create
    GET    /tasks       list, filterable and paged
    GET    /tasks/{id}  read one
    PUT    /tasks/{id}  replace
    PATCH  /tasks/{id}  edit some fields
    DELETE /tasks/{id}  remove

Run it with:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, status as http

from . import crud
from .database import get_db, init_db
from .models import Status, Task, TaskCreate, TaskPatch, TaskReplace


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Task API",
    description="A small CRUD API over a single tasks resource.",
    version="1.0.0",
    lifespan=lifespan,
)


def _found(task: dict | None, task_id: int) -> dict:
    """Every by-id route needs the same 404, worded the same way."""
    if task is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, f"No task with id {task_id}")
    return task


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/tasks", response_model=Task, status_code=http.HTTP_201_CREATED, tags=["tasks"])
def create_task(payload: TaskCreate) -> dict:
    """Create a task. Responds 201 with the stored row, ids and timestamps included."""
    with get_db() as conn:
        return crud.create(conn, payload.model_dump(mode="json"))


@app.get("/tasks", response_model=list[Task], tags=["tasks"])
def list_tasks(
    status: Status | None = Query(default=None, description="Only tasks in this status."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List tasks, newest first. Paged so the response cannot grow unbounded."""
    with get_db() as conn:
        return crud.list_all(conn, status.value if status else None, limit, offset)


@app.get("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def get_task(task_id: int) -> dict:
    with get_db() as conn:
        return _found(crud.get(conn, task_id), task_id)


@app.put("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def replace_task(task_id: int, payload: TaskReplace) -> dict:
    """Replace every field. A missing field is a 422, not a silent keep."""
    with get_db() as conn:
        return _found(crud.replace(conn, task_id, payload.model_dump(mode="json")), task_id)


@app.patch("/tasks/{task_id}", response_model=Task, tags=["tasks"])
def edit_task(task_id: int, payload: TaskPatch) -> dict:
    """Edit some fields. `exclude_unset` is what keeps an omitted field from
    being written as null — sending nothing means "leave it alone"."""
    changes = payload.model_dump(mode="json", exclude_unset=True)
    with get_db() as conn:
        return _found(crud.patch(conn, task_id, changes), task_id)


@app.delete("/tasks/{task_id}", status_code=http.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(task_id: int) -> None:
    with get_db() as conn:
        if not crud.delete(conn, task_id):
            raise HTTPException(http.HTTP_404_NOT_FOUND, f"No task with id {task_id}")
