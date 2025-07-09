from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import Answer
from app.schemas import AnswerCreate, AnswerUpdate
from app.dependencies import get_db

router = APIRouter()

@router.get("/answers")
def list_answers(db: Session = Depends(get_db)):
    answers = db.query(Answer).all()
    return [
        {"id": a.id, "call_id": a.call_id, "question_id": a.question_id, "audio_url": a.audio_url, "transcript": a.transcript, "timestamp": a.timestamp}
        for a in answers
    ]

@router.get("/answers/{answer_id}")
def get_answer(answer_id: int, db: Session = Depends(get_db)):
    answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    return {"id": answer.id, "call_id": answer.call_id, "question_id": answer.question_id, "audio_url": answer.audio_url, "transcript": answer.transcript, "timestamp": answer.timestamp}

@router.post("/answers")
def create_answer(answer: AnswerCreate, db: Session = Depends(get_db)):
    db_answer = Answer(call_id=answer.call_id, question_id=answer.question_id, audio_url=answer.audio_url, transcript=answer.transcript)
    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return {"id": db_answer.id, "call_id": db_answer.call_id, "question_id": db_answer.question_id, "audio_url": db_answer.audio_url, "transcript": db_answer.transcript, "timestamp": db_answer.timestamp}

@router.put("/answers/{answer_id}")
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

@router.delete("/answers/{answer_id}")
def delete_answer(answer_id: int, db: Session = Depends(get_db)):
    db_answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not db_answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    db.delete(db_answer)
    db.commit()
    return {"detail": "Answer deleted"} 