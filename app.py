from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
import os
from config import TELNYX_API_KEY, TELNYX_PHONE_NUMBER
import telnyx
from db import SessionLocal, Candidate, Question, Call, Answer
from sqlalchemy.orm import Session

from typing import Optional

app = FastAPI()

telnyx.api_key = TELNYX_API_KEY

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class CandidateCreate(BaseModel):
    name: str
    phone: str
    role: str

class CandidateUpdate(BaseModel):
    name: str = None
    phone: str = None
    role: str = None

class QuestionCreate(BaseModel):
    text: str
    role: str
    order: int

class QuestionUpdate(BaseModel):
    text: str = None
    role: str = None
    order: int = None

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

@app.get("/candidates")
def list_candidates(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return [
        {"id": c.id, "name": c.name, "phone": c.phone, "role": c.role}
        for c in candidates
    ]

@app.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"id": candidate.id, "name": candidate.name, "phone": candidate.phone, "role": candidate.role}

@app.post("/candidates")
def create_candidate(candidate: CandidateCreate, db: Session = Depends(get_db)):
    db_candidate = Candidate(name=candidate.name, phone=candidate.phone, role=candidate.role)
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return {"id": db_candidate.id, "name": db_candidate.name, "phone": db_candidate.phone, "role": db_candidate.role}

@app.put("/candidates/{candidate_id}")
def update_candidate(candidate_id: int, candidate: CandidateUpdate, db: Session = Depends(get_db)):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.name is not None:
        db_candidate.name = candidate.name
    if candidate.phone is not None:
        db_candidate.phone = candidate.phone
    if candidate.role is not None:
        db_candidate.role = candidate.role
    db.commit()
    db.refresh(db_candidate)
    return {"id": db_candidate.id, "name": db_candidate.name, "phone": db_candidate.phone, "role": db_candidate.role}

@app.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(db_candidate)
    db.commit()
    return {"detail": "Candidate deleted"}

@app.get("/questions")
def list_questions(db: Session = Depends(get_db)):
    questions = db.query(Question).all()
    return [
        {"id": q.id, "text": q.text, "role": q.role, "order": q.order}
        for q in questions
    ]

@app.get("/questions/{question_id}")
def get_question(question_id: int, db: Session = Depends(get_db)):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"id": question.id, "text": question.text, "role": question.role, "order": question.order}

@app.post("/questions")
def create_question(question: QuestionCreate, db: Session = Depends(get_db)):
    db_question = Question(text=question.text, role=question.role, order=question.order)
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return {"id": db_question.id, "text": db_question.text, "role": db_question.role, "order": db_question.order}

@app.put("/questions/{question_id}")
def update_question(question_id: int, question: QuestionUpdate, db: Session = Depends(get_db)):
    db_question = db.query(Question).filter(Question.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    if question.text is not None:
        db_question.text = question.text
    if question.role is not None:
        db_question.role = question.role
    if question.order is not None:
        db_question.order = question.order
    db.commit()
    db.refresh(db_question)
    return {"id": db_question.id, "text": db_question.text, "role": db_question.role, "order": db_question.order}

@app.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    db_question = db.query(Question).filter(Question.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(db_question)
    db.commit()
    return {"detail": "Question deleted"}

@app.get("/calls")
def list_calls(db: Session = Depends(get_db)):
    calls = db.query(Call).all()
    return [
        {"id": c.id, "candidate_id": c.candidate_id, "started_at": c.started_at, "completed_at": c.completed_at, "status": c.status}
        for c in calls
    ]

@app.get("/calls/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return {"id": call.id, "candidate_id": call.candidate_id, "started_at": call.started_at, "completed_at": call.completed_at, "status": call.status}

@app.post("/calls")
def create_call(call: CallCreate, db: Session = Depends(get_db)):
    db_call = Call(candidate_id=call.candidate_id, status=call.status)
    db.add(db_call)
    db.commit()
    db.refresh(db_call)
    return {"id": db_call.id, "candidate_id": db_call.candidate_id, "started_at": db_call.started_at, "completed_at": db_call.completed_at, "status": db_call.status}

@app.put("/calls/{call_id}")
def update_call(call_id: int, call: CallUpdate, db: Session = Depends(get_db)):
    db_call = db.query(Call).filter(Call.id == call_id).first()
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.status is not None:
        db_call.status = call.status
    if call.completed_at is not None:
        db_call.completed_at = call.completed_at
    db.commit()
    db.refresh(db_call)
    return {"id": db_call.id, "candidate_id": db_call.candidate_id, "started_at": db_call.started_at, "completed_at": db_call.completed_at, "status": db_call.status}

@app.delete("/calls/{call_id}")
def delete_call(call_id: int, db: Session = Depends(get_db)):
    db_call = db.query(Call).filter(Call.id == call_id).first()
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    db.delete(db_call)
    db.commit()
    return {"detail": "Call deleted"}

@app.get("/answers")
def list_answers(db: Session = Depends(get_db)):
    answers = db.query(Answer).all()
    return [
        {"id": a.id, "call_id": a.call_id, "question_id": a.question_id, "audio_url": a.audio_url, "transcript": a.transcript, "timestamp": a.timestamp}
        for a in answers
    ]

@app.get("/answers/{answer_id}")
def get_answer(answer_id: int, db: Session = Depends(get_db)):
    answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"id": answer.id, "call_id": answer.call_id, "question_id": answer.question_id, "audio_url": answer.audio_url, "transcript": answer.transcript, "timestamp": answer.timestamp}

@app.post("/answers")
def create_answer(answer: AnswerCreate, db: Session = Depends(get_db)):
    db_answer = Answer(call_id=answer.call_id, question_id=answer.question_id, audio_url=answer.audio_url, transcript=answer.transcript)
    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return {"id": db_answer.id, "call_id": db_answer.call_id, "question_id": db_answer.question_id, "audio_url": db_answer.audio_url, "transcript": db_answer.transcript, "timestamp": db_answer.timestamp}

@app.put("/answers/{answer_id}")
def update_answer(answer_id: int, answer: AnswerUpdate, db: Session = Depends(get_db)):
    db_answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not db_answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.audio_url is not None:
        db_answer.audio_url = answer.audio_url
    if answer.transcript is not None:
        db_answer.transcript = answer.transcript
    db.commit()
    db.refresh(db_answer)
    return {"id": db_answer.id, "call_id": db_answer.call_id, "question_id": db_answer.question_id, "audio_url": db_answer.audio_url, "transcript": db_answer.transcript, "timestamp": db_answer.timestamp}

@app.delete("/answers/{answer_id}")
def delete_answer(answer_id: int, db: Session = Depends(get_db)):
    db_answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not db_answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    db.delete(db_answer)
    db.commit()
    return {"detail": "Answer deleted"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/call/start")
def start_call(phone: str):
    try:
        call = telnyx.Call.create(
            connection_id="YOUR_CONNECTION_ID",  
            to=phone,
            from_=TELNYX_PHONE_NUMBER,
            webhook_url="https://your-server.com/telnyx/answer"
        )
        return JSONResponse({"status": "initiated", "call_control_id": call.call_control_id})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)

@app.post("/telnyx/answer")
async def telnyx_answer(request: Request):
    return JSONResponse({
        "actions": [
            {"say": {"payload": "Hello, this is the automated HR interview system. Please wait while we begin your interview."}},
            {"record_start": {}}
        ]
    })

