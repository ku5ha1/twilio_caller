from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi import Form, UploadFile, File
import pandas as pd
from app.api.candidates import router as candidates_router
from app.api.questions import router as questions_router
from app.api.calls import router as calls_router
from app.api.answers import router as answers_router
from app.api.tts import router as tts_router
from app.api.interview import router as interview_router
from app.models import Candidate, Question, Call, Answer
from app.dependencies import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
from sqlalchemy.exc import IntegrityError

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

app.include_router(candidates_router)
app.include_router(questions_router)
app.include_router(calls_router)
app.include_router(answers_router)
app.include_router(tts_router)
app.include_router(interview_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/candidates-html")
def candidates_html(request: Request, db: Session = Depends(get_db)):
    candidates = db.query(Candidate).all()
    return templates.TemplateResponse("candidates.html", {"request": request, "candidates": candidates})

@app.get("/questions-html")
def questions_html(request: Request, db: Session = Depends(get_db)):
    questions = db.query(Question).all()
    return templates.TemplateResponse("questions.html", {"request": request, "questions": questions})

@app.get("/calls-html")
def calls_html(request: Request, db: Session = Depends(get_db)):
    calls = db.query(Call).all()
    return templates.TemplateResponse("calls.html", {"request": request, "calls": calls})

@app.get("/answers-html")
def answers_html(request: Request, db: Session = Depends(get_db)):
    answers = db.query(Answer).all()
    return templates.TemplateResponse("answers.html", {"request": request, "answers": answers})

@app.get("/upload-candidates")
def upload_candidates_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request, "message": None, "success": True})

@app.post("/upload-candidates")
def upload_candidates(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        df = pd.read_excel(file.file)
        added, skipped = 0, 0
        for _, row in df.iterrows():
            name = row.get("Name of Candidate") or row.get("Name")
            phone = str(row.get("contact details") or row.get("Contact Details") or row.get("contact number") or row.get("Contact Number"))
            role = row.get("Remarks")
            if not name or not phone:
                skipped += 1
                continue
            existing = db.query(Candidate).filter_by(phone=phone).first()
            if not existing:
                candidate = Candidate(name=name, phone=phone, role=role)
                db.add(candidate)
                added += 1
            else:
                skipped += 1
        db.commit()
        message = f"Added {added} candidates. Skipped {skipped} (already present or missing data)."
        return templates.TemplateResponse("upload.html", {"request": request, "message": message, "success": True})
    except Exception as e:
        return templates.TemplateResponse("upload.html", {"request": request, "message": f'Error: {e}', "success": False}) 