from datetime import date

from pydantic import BaseModel, EmailStr, Field


class RecipientInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    course: str = Field(min_length=1, max_length=200)


class GenerationJobCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=200)
    certificate_title: str = Field(
        default="Certificate of Participation",
        min_length=1,
        max_length=200,
    )
    completion_date: date = Field(default_factory=date.today)
    recipients: list[dict] = Field(min_length=1)


class RecipientStatusResponse(BaseModel):
    recipient_id: str
    name: str
    email: str
    status: str
    certificate_id: str | None = None
    error_message: str | None = None
    download_url: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total: int
    pending: int
    processing: int
    successful: int
    failed: int
    progress_percent: float
    certificates: list[RecipientStatusResponse]