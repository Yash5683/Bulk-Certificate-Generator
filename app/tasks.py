from .celery_app import celery_app
from .services import process_job


@celery_app.task(name="app.tasks.bulk_generate")
def bulk_generate(job_id: str):
    return process_job(job_id)
