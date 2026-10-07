from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./certificates.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass


def ensure_database_schema():
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "recipients" not in inspector.get_table_names():
        return

    recipient_columns = {column["name"] for column in inspector.get_columns("recipients")}
    if "completion_date" not in recipient_columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE recipients ADD COLUMN completion_date DATE NOT NULL DEFAULT CURRENT_DATE"
            ))


ensure_database_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
