from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .certificate import OUTPUT_DIR
from .database import Base, engine, get_db
from .models import GenerationJob, JobStatus, Recipient, RecipientStatus
from .schemas import (
    GenerationJobCreate,
    JobStatusResponse,
    RecipientInput,
    RecipientStatusResponse,
)
from .services import process_job


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Bulk Certificate Generator",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_job(
    payload: GenerationJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job = GenerationJob(
        event_name=payload.event_name,
        certificate_title=payload.certificate_title,
    )

    valid_recipients = 0

    for item in payload.recipients:
        try:
            recipient_input = RecipientInput.model_validate(item)

            recipient = Recipient(
                name=recipient_input.name.strip(),
                email=str(recipient_input.email).lower(),
                course=recipient_input.course.strip(),
                completion_date=payload.completion_date,
                status=RecipientStatus.PENDING,
            )

            job.recipients.append(recipient)
            valid_recipients += 1

        except (ValidationError, TypeError, ValueError) as exc:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()[:100]
                email = str(item.get("email", "")).strip()[:320].lower()
                course = str(item.get("course", "")).strip()[:200]
            else:
                name = ""
                email = ""
                course = ""

            error_message = (
                exc.errors()[0]["msg"]
                if isinstance(exc, ValidationError)
                else str(exc)
            )

            job.recipients.append(
                Recipient(
                    name=name,
                    email=email,
                    course=course,
                    completion_date=payload.completion_date,
                    status=RecipientStatus.INVALID,
                    error_message=error_message,
                )
            )

    db.add(job)
    db.commit()
    db.refresh(job)

    if valid_recipients > 0:
        job.status = JobStatus.PENDING
        db.commit()

        background_tasks.add_task(process_job, job.id)
    else:
        job.status = JobStatus.FAILED
        db.commit()

    return {
        "job_id": job.id,
        "status": job.status.value,
        "message": (
            "Certificate generation job accepted."
            if valid_recipients > 0
            else "Certificate generation job failed: all recipients are invalid."
        ),
        "status_url": f"/api/v1/jobs/{job.id}",
        "total": len(job.recipients),
    }


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.get(GenerationJob, job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    recipients = list(job.recipients)

    total = len(recipients)
    pending = sum(
        r.status == RecipientStatus.PENDING
        for r in recipients
    )
    processing = sum(
        r.status == RecipientStatus.PROCESSING
        for r in recipients
    )
    successful = sum(
        r.status == RecipientStatus.SUCCESS
        for r in recipients
    )
    failed = sum(
        r.status in (
            RecipientStatus.FAILED,
            RecipientStatus.INVALID,
        )
        for r in recipients
    )

    completed = successful + failed

    progress = (
        round((completed / total) * 100, 2)
        if total
        else 0
    )

    certificate_items = []

    for recipient in recipients:
        certificate_items.append(
            RecipientStatusResponse(
                recipient_id=recipient.id,
                name=recipient.name,
                email=recipient.email,
                status=recipient.status.value,
                certificate_id=recipient.certificate_id,
                error_message=recipient.error_message,
                download_url=(
                    f"/api/v1/certificates/{recipient.certificate_id}"
                    if recipient.certificate_id
                    and recipient.status == RecipientStatus.SUCCESS
                    else None
                ),
            )
        )

    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        total=total,
        pending=pending,
        processing=processing,
        successful=successful,
        failed=failed,
        progress_percent=progress,
        certificates=certificate_items,
    )


@app.get("/api/v1/certificates/{certificate_id}")
def get_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    recipient = (
        db.query(Recipient)
        .filter(
            Recipient.certificate_id == certificate_id,
            Recipient.status == RecipientStatus.SUCCESS,
        )
        .first()
    )

    if not recipient:
        raise HTTPException(
            status_code=404,
            detail="Generated certificate not found.",
        )

    path = OUTPUT_DIR / f"{certificate_id}.pdf"

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Certificate file is unavailable.",
        )

    filename = (
        f"{recipient.name.replace(' ', '_')}_certificate.pdf"
    )

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=filename,
    )