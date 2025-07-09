from pydantic import BaseModel
from typing import Optional

class CandidateCreate(BaseModel):
    name: str
    phone: str
    role: str

class CandidateUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None

class QuestionCreate(BaseModel):
    text: str
    role: str
    order: int

class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    role: Optional[str] = None
    order: Optional[int] = None

class CallCreate(BaseModel):
    candidate_id: int
    status: Optional[str] = "scheduled"

class CallUpdate(BaseModel):
    status: Optional[str] = None
    completed_at: Optional[str] = None

class AnswerCreate(BaseModel):
    call_id: int
    question_id: int
    audio_url: Optional[str] = None
    transcript: Optional[str] = None

class AnswerUpdate(BaseModel):
    audio_url: Optional[str] = None
    transcript: Optional[str] = None 