from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from core.config import settings

if not settings.POSTGRES_URI:
    raise ValueError("CRITICAL: POSTGRES_URI is not configured in the environment.")

# Initialize connection pool for PostgreSQL
engine = create_engine(
    settings.POSTGRES_URI,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Establish session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Modern SQLAlchemy 2.0 Declarative Base
class Base(DeclarativeBase):
    pass

def get_db():
    """Dependency for FastAPI endpoints to yield and close DB sessions securely."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
