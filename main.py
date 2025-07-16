from fastapi import FastAPI
from routes import call_router
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Twilio Caller")
app.mount("/media", StaticFiles(directory="media"), name="media")
app.include_router(call_router.router)

@app.get("/")
def read_root():
    return {"message": "HR VoiceBot is running!"}