# aidcare_pipeline/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import os
from dotenv import load_dotenv

load_dotenv() # Ensures .env is loaded if this module is accessed early

SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    # Railway-first fallback: allow app startup even when a Postgres plugin is not attached yet.
    # Set AIDCARE_ALLOW_SQLITE_FALLBACK=0 to force DATABASE_URL requirement.
    allow_sqlite_fallback = os.getenv("AIDCARE_ALLOW_SQLITE_FALLBACK", "1").lower() in {"1", "true", "yes"}
    if not allow_sqlite_fallback:
        raise RuntimeError("CRITICAL: DATABASE_URL environment variable not set!")

    sqlite_path = os.getenv("AIDCARE_SQLITE_PATH", "./aidcare_fallback.db")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{sqlite_path}"
    print(
        "WARNING: DATABASE_URL not set. "
        f"Using SQLite fallback at {sqlite_path}. "
        "Attach Railway Postgres and set DATABASE_URL for persistent production data."
    )

# echo=True will log all SQL statements executed by SQLAlchemy - useful for debugging
# Set to False for production
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base() # This Base will be imported by your models file

# Dependency to get a DB session in FastAPI routes
def get_db() -> Session: # type: ignore # Type hint for editor support
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
