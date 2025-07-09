from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import Candidate
from app.schemas import CandidateCreate, CandidateUpdate
from app.dependencies import get_db

router = APIRouter()

@router.get("/candidates")
def list_candidates(db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return [
        {"id": c.id, "name": c.name, "phone": c.phone, "role": c.role}
        for c in candidates
    ]

@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"id": candidate.id, "name": candidate.name, "phone": candidate.phone, "role": candidate.role}

@router.post("/candidates")
def create_candidate(candidate: CandidateCreate, db: Session = Depends(get_db)):
    db_candidate = Candidate(name=candidate.name, phone=candidate.phone, role=candidate.role)
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return {"id": db_candidate.id, "name": db_candidate.name, "phone": db_candidate.phone, "role": db_candidate.role}

@router.put("/candidates/{candidate_id}")
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

@router.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(db_candidate)
    db.commit()
    return {"detail": "Candidate deleted"} 