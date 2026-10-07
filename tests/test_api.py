from datetime import date
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.certificate import OUTPUT_DIR, generate_certificate
from app.database import Base, get_db
from app.main import app
from app.models import GenerationJob, RecipientStatus
from app.services import process_job

engine=create_engine("sqlite:///./test_certificates.db",connect_args={"check_same_thread":False})
Session=sessionmaker(bind=engine,autoflush=False,autocommit=False)

def override():
    db=Session()
    try: yield db
    finally: db.close()

@pytest.fixture(autouse=True)
def setup(monkeypatch):
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    app.dependency_overrides[get_db]=override
    monkeypatch.setattr("app.main.celery_app.send_task", Mock())
    monkeypatch.setattr("app.services.SessionLocal", Session)
    yield
    app.dependency_overrides.clear()
    for p in OUTPUT_DIR.glob("*.pdf"): p.unlink(missing_ok=True)

def client(): return TestClient(app)

def payload():
    return {
        "event_name":"AI Workshop 2026",
        "certificate_title":"Certificate of Participation",
        "completion_date":"2026-10-07",
        "recipients":[
            {"full_name":"Aarav Sharma","email":"aarav@example.com","course":"Artificial Intelligence"},
            {"full_name":"Priya Rao","email":"priya@example.com","course":"Machine Learning"},
        ],
    }

def test_create_generation_job_accepts_exact_request():
    response=client().post("/jobs/",json=payload())
    assert response.status_code==202
    body=response.json()
    assert body["job_id"] and body["status"]=="PENDING" and body["total"]==2


def test_invalid_recipient_is_recorded_and_not_queued(monkeypatch):
    from app import main
    enqueue=Mock()
    monkeypatch.setattr(main.celery_app,"send_task",enqueue)
    invalid_payload={
        "event_name":"AI Workshop 2026",
        "certificate_title":"Certificate of Participation",
        "completion_date":"2026-10-07",
        "recipients":[
            {"full_name":"Aarav Sharma","email":"not-an-email","course":"Artificial Intelligence"},
            {"full_name":"Priya Rao","email":"priya@example.com","course":""},
        ],
    }
    response=client().post("/jobs/",json=invalid_payload)
    assert response.status_code==202
    enqueue.assert_not_called()
    job=client().get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"]=="FAILED" and job["total"]==2 and job["failed"]==0
    assert {item["status"] for item in job["certificates"]} == {"INVALID"}


def test_mixed_batch_is_persisted_and_only_valid_recipients_are_queued(monkeypatch):
    from app import main
    enqueue=Mock()
    monkeypatch.setattr(main.celery_app,"send_task",enqueue)
    mixed_payload=payload()
    mixed_payload["recipients"].append({"full_name":"Bad","email":"bad","course":"Course"})
    response=client().post("/jobs/",json=mixed_payload)
    assert response.status_code==202
    enqueue.assert_called_once()
    job=client().get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["total"]==3 and job["pending"]==2 and job["successful"]==0
    assert {item["status"] for item in job["certificates"]} == {"PENDING", "INVALID"}


def test_certificate_generation():
    path=generate_certificate(certificate_id="unit-test",recipient_name="Test User",course="Python",event_name="Event",certificate_title="Certificate",completion_date=date(2026,10,7))
    assert path.exists() and path.stat().st_size>1000
    path.unlink()


def test_job_status_progress():
    c=client(); job_id=c.post("/jobs/",json=payload()).json()["job_id"]
    process_job(job_id)
    job=c.get(f"/api/v1/jobs/{job_id}").json()
    assert job["total"]==2 and job["successful"]==2 and job["progress_percent"]==100 and job["status"]=="COMPLETED"


def test_individual_failure_is_isolated(monkeypatch):
    import app.services as s
    original=s.generate_certificate
    def fail(**kwargs):
        if kwargs["recipient_name"]=="Priya Rao": raise RuntimeError("Simulated PDF failure")
        return original(**kwargs)
    monkeypatch.setattr(s,"generate_certificate",fail)
    c=client(); job_id=c.post("/jobs/",json=payload()).json()["job_id"]
    process_job(job_id)
    job=c.get(f"/api/v1/jobs/{job_id}").json()
    items={item["name"]:item for item in job["certificates"]}
    assert job["successful"]==1 and job["failed"]==1 and job["status"]=="COMPLETED_WITH_ERRORS"
    assert items["Aarav Sharma"]["status"]=="SUCCESS" and items["Priya Rao"]["status"]=="FAILED"


def test_retrieve_generated_certificate():
    c=client(); job_id=c.post("/jobs/",json=payload()).json()["job_id"]
    process_job(job_id)
    certificate_id=next(item["certificate_id"] for item in c.get(f"/api/v1/jobs/{job_id}").json()["certificates"] if item["status"]=="SUCCESS")
    response=c.get(f"/api/v1/certificates/{certificate_id}")
    assert response.status_code==200 and response.headers["content-type"].startswith("application/pdf") and response.content.startswith(b"%PDF")
