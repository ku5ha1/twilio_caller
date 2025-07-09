from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import Candidate, Call, Question, Answer
from app.schemas import AnswerCreate
from app.dependencies import get_db
from typing import Optional
import datetime

router = APIRouter()

@router.post("/interview/start")
def start_interview(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    # Create a new call/interview session
    call = Call(candidate_id=candidate_id, status="in_progress")
    db.add(call)
    db.commit()
    db.refresh(call)
    # Get first question for the candidate's role, ordered by 'order'
    question = db.query(Question).filter(Question.role == candidate.role).order_by(Question.order).first()
    if not question:
        raise HTTPException(status_code=404, detail="No questions found for this role")
    return {"call_id": call.id, "question": {"id": question.id, "text": question.text, "order": question.order}}

@router.post("/interview/next")
def next_question(call_id: int, question_id: int, audio_url: Optional[str] = None, transcript: Optional[str] = None, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    # Store the answer
    answer = Answer(call_id=call_id, question_id=question_id, audio_url=audio_url, transcript=transcript)
    db.add(answer)
    db.commit()
    # Find the next question for this role
    current_question = db.query(Question).filter(Question.id == question_id).first()
    if not current_question:
        raise HTTPException(status_code=404, detail="Question not found")
    next_q = db.query(Question).filter(
        Question.role == current_question.role,
        Question.order > current_question.order
    ).order_by(Question.order).first()
    if next_q:
        return {"next_question": {"id": next_q.id, "text": next_q.text, "order": next_q.order}}
    else:
        # No more questions, mark call as completed
        call.status = "completed"
        call.completed_at = datetime.datetime.utcnow()
        db.commit()
        return {"detail": "Interview complete"}

@router.post("/interview/finish")
def finish_interview(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    call.status = "completed"
    call.completed_at = datetime.datetime.utcnow()
    db.commit()
    return {"detail": "Interview marked as complete"} 