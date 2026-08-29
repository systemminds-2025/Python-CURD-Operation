# Task API

A small CRUD API over a single `tasks` resource — FastAPI, SQLite, no ORM.

## Run it

```bash
cd ~/Downloads/task-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs> for the interactive docs — every endpoint
below is callable from that page.

## The six endpoints

| Method   | Path          | Does                                  | Success |
|----------|---------------|---------------------------------------|---------|
| `POST`   | `/tasks`      | Create a task                         | 201     |
| `GET`    | `/tasks`      | List tasks, newest first              | 200     |
| `GET`    | `/tasks/{id}` | Read one                              | 200     |
| `PUT`    | `/tasks/{id}` | Replace every field                   | 200     |
| `PATCH`  | `/tasks/{id}` | Edit some fields                      | 200     |
| `DELETE` | `/tasks/{id}` | Remove it                             | 204     |

`GET /health` is there too, for a liveness check.

### PUT vs PATCH

They are deliberately different, which is why there are two.

- `PUT` is a **replacement**: send every field. Leaving one out is a 422, not a
  silent keep — otherwise a partial body would quietly blank the fields you
  forgot.
- `PATCH` is an **edit**: send only what changes. Omitted fields are left alone.

### List parameters

| Param    | Default | Notes                                        |
|----------|---------|----------------------------------------------|
| `status` | —       | `todo`, `in_progress` or `done`              |
| `limit`  | 50      | 1–200                                        |
| `offset` | 0       | For paging                                   |

## Try it

```bash
# create
curl -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Ship the API","priority":"high"}'

# list, and filter
curl http://127.0.0.1:8000/tasks
curl 'http://127.0.0.1:8000/tasks?status=done&limit=10'

# read, replace, edit, delete
curl http://127.0.0.1:8000/tasks/1
curl -X PUT   http://127.0.0.1:8000/tasks/1 -H 'Content-Type: application/json' \
  -d '{"title":"Ship it","description":"","status":"done","priority":"low"}'
curl -X PATCH http://127.0.0.1:8000/tasks/1 -H 'Content-Type: application/json' \
  -d '{"status":"in_progress"}'
curl -X DELETE http://127.0.0.1:8000/tasks/1
```

## Tests

```bash
python3 -m pytest tests -q
```

Ten tests covering all six endpoints, including the cases that are easy to get
wrong: a `PUT` missing a field, a `PATCH` that must not blank what it omits, and
a delete that 404s the second time.

## Layout

```
app/
  main.py      routes, and the HTTP-level rules
  models.py    request and response shapes
  crud.py      SQL, returning plain dicts
  database.py  connection handling and schema
tests/
  test_api.py
```

The data layer returns dicts and knows nothing about HTTP; the routes own the
status codes. The database file (`tasks.db`) is created next to this README on
first run and is gitignored.
