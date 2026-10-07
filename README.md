# Bulk Certificate Generator

FastAPI backend for bulk certificate generation with SQLite/SQLAlchemy, background processing, per-recipient status, PDF generation, and tests.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

## Create a job

`POST /api/v1/jobs`

```json
{"event_name":"AI Workshop 2026","certificate_title":"Certificate of Participation","recipients":[{"name":"Aarav Sharma","email":"aarav@example.com","course":"Artificial Intelligence"},{"name":"Priya Rao","email":"priya@example.com","course":"Machine Learning"}]}
```

The endpoint returns `202 Accepted` and a `job_id`.

## Track progress

`GET /api/v1/jobs/{job_id}` returns total, pending, processing, successful, failed, percentage progress, and each recipient's status/error/download URL.

## Retrieve certificate

`GET /api/v1/certificates/{certificate_id}` returns the generated PDF.

## Tests

```bash
pytest -q
```

## Design decisions

- One request creates one persisted job instead of one request per certificate.
- Background processing prevents a large batch from blocking the HTTP request.
- Each recipient is processed independently; exceptions are caught and persisted as failures.
- A job is `COMPLETED_WITH_ERRORS` for partial success and `FAILED` when every certificate fails.
- The template is intentionally fixed because the assignment requires one predefined template.
- SQLite is used for easy local setup; PostgreSQL/object storage and a durable queue would be appropriate production upgrades.
- Each background run creates its own DB session rather than reusing a request session.
