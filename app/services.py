from .certificate import generate_certificate
from .database import SessionLocal
from .models import GenerationJob, JobStatus, RecipientStatus


def process_job(job_id: str):
    db=SessionLocal()
    try:
        job=db.get(GenerationJob,job_id)
        if not job:return
        job.status=JobStatus.PROCESSING; db.commit()
        recipients=list(job.recipients)
        for recipient in recipients:
            if recipient.status == RecipientStatus.INVALID:
                continue
            recipient.status=RecipientStatus.PROCESSING; db.commit()
            try:
                certificate_id=recipient.certificate_id or recipient.id
                generate_certificate(certificate_id=certificate_id,recipient_name=recipient.name,course=recipient.course,event_name=job.event_name,certificate_title=job.certificate_title,completion_date=recipient.completion_date)
                recipient.certificate_id=certificate_id; recipient.status=RecipientStatus.SUCCESS; recipient.error_message=None; db.commit()
            except Exception as exc:
                recipient.status=RecipientStatus.FAILED; recipient.error_message=str(exc)[:1000]; db.commit()
        successful=sum(r.status==RecipientStatus.SUCCESS for r in recipients); failed=sum(r.status==RecipientStatus.FAILED for r in recipients); invalid=sum(r.status==RecipientStatus.INVALID for r in recipients)
        if successful == len(recipients) - invalid:
            job.status=JobStatus.COMPLETED
        elif successful == 0 and failed == 0:
            job.status=JobStatus.FAILED
        else:
            job.status=JobStatus.COMPLETED_WITH_ERRORS
        db.commit()
    finally: db.close()
