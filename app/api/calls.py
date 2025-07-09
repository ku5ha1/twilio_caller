from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import Call
from app.schemas import CallCreate, CallUpdate
from app.dependencies import get_db

router = APIRouter()

@router.get("/calls")
def list_calls(db: Session = Depends(get_db)):
    calls = db.query(Call).all()
    return [
        {"id": c.id, "candidate_id": c.candidate_id, "started_at": c.started_at, "completed_at": c.completed_at, "status": c.status}
        for c in calls
    ]

@router.get("/calls/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return {"id": call.id, "candidate_id": call.candidate_id, "started_at": call.started_at, "completed_at": call.completed_at, "status": call.status}

@router.post("/calls")
def create_call(call: CallCreate, db: Session = Depends(get_db)):
    db_call = Call(candidate_id=call.candidate_id, status=call.status)
    db.add(db_call)
    db.commit()
    db.refresh(db_call)
    return {"id": db_call.id, "candidate_id": db_call.candidate_id, "started_at": db_call.started_at, "completed_at": db_call.completed_at, "status": db_call.status}

@router.put("/calls/{call_id}")
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

@router.delete("/calls/{call_id}")
def delete_call(call_id: int, db: Session = Depends(get_db)):
    db_call = db.query(Call).filter(Call.id == call_id).first()
    if not db_call:
        raise HTTPException(status_code=404, detail="Call not found")
    db.delete(db_call)
    db.commit()
    return {"detail": "Call deleted"} 