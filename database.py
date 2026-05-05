import os
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database configuration for local and Render deployment
DATABASE_URL = "sqlite:///./biopath_ai.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Opportunity(Base):
    """
    Data model for Biotechnology opportunities including Jobs, MSc, PhDs, Internships, and Workshops.
    """
    __tablename__ = "opportunities"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(String)  # Job, Masters, PhD, Internship, Workshop
    field = Column(String)     # e.g., Bioinformatics, Genetics
    eligibility = Column(String)
    skills_required = Column(String) # Comma-separated list
    location = Column(String)
    uploaded_date = Column(String)     # NEW
    deadline = Column(String)
    exams_required = Column(String)    # NEW
    fellowship_details = Column(String)# NEW
    link = Column(String)
    description = Column(Text)

def init_db():
    """Initializes the database and creates all tables."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Creates a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()