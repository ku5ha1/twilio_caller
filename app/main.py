from fastapi import FastAPI
from app.api.candidates import router as candidates_router
from app.api.questions import router as questions_router
from app.api.calls import router as calls_router
from app.api.answers import router as answers_router
from app.api.tts import router as tts_router

app = FastAPI()

app.include_router(candidates_router)
app.include_router(questions_router)
app.include_router(calls_router)
app.include_router(answers_router)
app.include_router(tts_router)

@app.get("/health")
def health_check():
    return {"status": "ok"} 