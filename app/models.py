import enum, uuid
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow(): return datetime.now(timezone.utc)
class JobStatus(str, enum.Enum):
    PENDING="PENDING"; PROCESSING="PROCESSING"; COMPLETED="COMPLETED"; COMPLETED_WITH_ERRORS="COMPLETED_WITH_ERRORS"; FAILED="FAILED"
class RecipientStatus(str, enum.Enum):
    PENDING="PENDING"; PROCESSING="PROCESSING"; SUCCESS="SUCCESS"; FAILED="FAILED"; INVALID="INVALID"
class GenerationJob(Base):
    __tablename__="generation_jobs"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    event_name: Mapped[str]=mapped_column(String(200))
    certificate_title: Mapped[str]=mapped_column(String(200))
    status: Mapped[JobStatus]=mapped_column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    recipients: Mapped[list["Recipient"]]=relationship(back_populates="job", cascade="all, delete-orphan")
class Recipient(Base):
    __tablename__="recipients"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    job_id: Mapped[str]=mapped_column(ForeignKey("generation_jobs.id"), nullable=False, index=True)
    name: Mapped[str]=mapped_column(String(100)); email: Mapped[str]=mapped_column(String(320)); course: Mapped[str]=mapped_column(String(200))
    completion_date: Mapped[date]=mapped_column(Date, nullable=False)
    status: Mapped[RecipientStatus]=mapped_column(Enum(RecipientStatus), default=RecipientStatus.PENDING, nullable=False)
    certificate_id: Mapped[str|None]=mapped_column(String(36), unique=True)
    error_message: Mapped[str|None]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
    job: Mapped[GenerationJob]=relationship(back_populates="recipients")
