# aidcare_pipeline/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import os
from dotenv import load_dotenv

load_dotenv() # Ensures .env is loaded if this module is accessed early

SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    # This will cause the app to fail on import if DATABASE_URL isn't set, which is good.
    raise RuntimeError("CRITICAL: DATABASE_URL environment variable not set!")

# echo=True will log all SQL statements executed by SQLAlchemy - useful for debugging
# Set to False for production
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False) # Set echo=True for dev if needed
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base() # This Base will be imported by your models file

# Dependency to get a DB session in FastAPI routes
def get_db() -> Session: # type: ignore # Type hint for editor support
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()