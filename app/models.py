"""Request and response shapes.

Create, replace and patch are separate models because they genuinely differ:
a PUT must carry every field, a PATCH may carry any subset, and the response
carries server-owned fields the client never sends.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Status(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskCreate(BaseModel):
    """POST body. Everything but the title has a sensible default."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    status: Status = Status.todo
    priority: Priority = Priority.medium


class TaskReplace(BaseModel):
    """PUT body — a full replacement, so nothing is optional."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=2000)
    status: Status
    priority: Priority


class TaskPatch(BaseModel):
    """PATCH body. Every field optional; omitted ones are left alone.

    `None` and "absent" have to stay distinguishable, which is why the caller's
    intent is read with `exclude_unset` rather than by testing for None.
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: Status | None = None
    priority: Priority | None = None


class Task(BaseModel):
    """What the API returns."""

    id: int
    title: str
    description: str
    status: Status
    priority: Priority
    created_at: datetime
    updated_at: datetime
