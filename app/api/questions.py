from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import Question
from app.schemas import QuestionCreate, QuestionUpdate
from app.dependencies import get_db

router = APIRouter()

@router.get("/questions")
def list_questions(db: Session = Depends(get_db)):
    questions = db.query(Question).all()
    return [
        {"id": q.id, "text": q.text, "role": q.role, "order": q.order}
        for q in questions
    ]

@router.get("/questions/{question_id}")
def get_question(question_id: int, db: Session = Depends(get_db)):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"id": question.id, "text": question.text, "role": question.role, "order": question.order}

@router.post("/questions")
def create_question(question: QuestionCreate, db: Session = Depends(get_db)):
    db_question = Question(text=question.text, role=question.role, order=question.order)
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return {"id": db_question.id, "text": db_question.text, "role": db_question.role, "order": db_question.order}

@router.put("/questions/{question_id}")
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

@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    db_question = db.query(Question).filter(Question.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(db_question)
    db.commit()
    return {"detail": "Question deleted"} 