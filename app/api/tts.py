from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.models import Question
from app.dependencies import get_db
from voice_generator import generate_speech
import os

router = APIRouter()

MEDIA_DIR = "media"
os.makedirs(MEDIA_DIR, exist_ok=True)

@router.post("/questions/{question_id}/generate_audio")
def generate_question_audio(question_id: int, db: Session = Depends(get_db)):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    audio_filename = f"question_{question_id}.mp3"
    audio_path = os.path.join(MEDIA_DIR, audio_filename)
    try:
        generate_speech(question.text, audio_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")
    return {"audio_url": f"/media/{audio_filename}"}

@router.get("/media/{filename}")
def get_audio_file(filename: str):
    file_path = os.path.join(MEDIA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="audio/mpeg") 