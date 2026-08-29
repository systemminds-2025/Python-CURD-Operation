# Task API

A small CRUD API over a single `tasks` resource — FastAPI and MongoDB.

## Run it

```bash
cd ~/Downloads/task-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then put your connection string in it
uvicorn app.main:app --reload
```

## Configuration

Everything is read from `.env`, which is gitignored — `.env.example` is the
committed template. Nothing has a credential as a default.

| Variable             | Default                     | Notes                                   |
|----------------------|-----------------------------|-----------------------------------------|
| `MONGODB_URI`        | `mongodb://localhost:27017` | The whole credential lives here         |
| `MONGODB_DB`         | `taskapi`                   | Database name                           |
| `MONGODB_COLLECTION` | `tasks`                     | Collection name                         |
| `MONGODB_TIMEOUT_MS` | `5000`                      | How long to wait for a server           |
| `APP_NAME`, `DEBUG`  | —                           |                                         |

An Atlas string pastes in unchanged:

```
MONGODB_URI="mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
```

A password containing `@ / : ?` must be percent-encoded, or it splits the URI
apart. `GET /health` reports the URI back with the password masked, so a wrong
host is visible without exposing the credential.

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

`GET /health` is there too — liveness, plus whether MongoDB is actually
reachable.

Ids are MongoDB ObjectIds rendered as 24-character strings. A malformed id is
a 404 rather than a 500: it is a miss, not a crash.

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

Twelve tests covering all six endpoints, including the cases that are easy to
get wrong: a `PUT` missing a field, a `PATCH` that must not blank what it omits,
a malformed id that must 404 rather than 500, and a delete that 404s the second
time.

Each test gets its own throwaway database, dropped afterwards, so the configured
one is never touched. Point them elsewhere with `TEST_MONGODB_URI`. They skip,
rather than fail, if no MongoDB is reachable.

## Layout

```
app/
  main.py      routes, and the HTTP-level rules
  config.py    settings, read from .env
  models.py    request and response shapes
  crud.py      collection queries, returning plain dicts
  database.py  the client, and the indexes
tests/
  test_api.py
```

The data layer returns dicts and knows nothing about HTTP; the routes own the
status codes. One `MongoClient` is shared by the process — it owns a connection
pool and is thread-safe, so one per request would build and tear down pools
continuously.
