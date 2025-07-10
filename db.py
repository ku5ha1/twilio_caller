from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import pandas as pd

DATABASE_URL = "sqlite:///./hr_calls.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False, unique=True)
    role = Column(String, nullable=False)
    calls = relationship("Call", back_populates="candidate")

class Call(Base):
    __tablename__ = "calls"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="scheduled")
    reschedule_time = Column(DateTime, nullable=True)
    call_recording_url = Column(String, nullable=True)  # NEW: store call recording URL
    candidate = relationship("Candidate", back_populates="calls")
    answers = relationship("Answer", back_populates="call")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    role = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    answers = relationship("Answer", back_populates="question")

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    audio_url = Column(String, nullable=True)
    transcript = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    call = relationship("Call", back_populates="answers")
    question = relationship("Question", back_populates="answers")

# Create tables
Base.metadata.create_all(bind=engine)

def import_candidates_from_excel(excel_path="candidates.xlsx"):
    session = SessionLocal()
    df = pd.read_excel(excel_path)
    for _, row in df.iterrows():
        name = row.get("Name of Candidate") or row.get("Name")
        phone = str(row.get("contact details") or row.get("Contact Details") or row.get("contact number") or row.get("Contact Number"))
        role = row.get("Remarks") 
        if not name or not phone:
            continue
        # Check if candidate already exists
        existing = session.query(Candidate).filter_by(phone=phone).first()
        if not existing:
            candidate = Candidate(name=name, phone=phone, role=role)
            session.add(candidate)
    session.commit()
    session.close() 