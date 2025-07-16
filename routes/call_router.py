from fastapi import APIRouter, Request, Response, BackgroundTasks
from urllib.parse import urlencode
from pydantic import BaseModel
from services import twilio_service, assemblyai_service
from dotenv import load_dotenv
import os
from utils.db_utils import get_mongo_collection
from services.assemblyai_service import transcribe_audio

load_dotenv()

HR_INTRO_AUDIO_URL = os.getenv('HR_INTRO_AUDIO_URL')

router = APIRouter()

class StartCallRequest(BaseModel):
    name: str
    phone: str

# List of question audio files in order
QUESTIONS = [f"question{i}.mp3" for i in range(1, 13)]

# Helper: Simple in-memory storage for answers (for demo)
CALL_STATE = {}

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
if not PUBLIC_BASE_URL:
    raise ValueError("PUBLIC_BASE_URL must be set in .env (e.g., https://your-app.onrender.com)")

# Consent analysis function
def is_positive_consent(transcript):
    transcript = transcript.lower()
    positive_keywords = ["yes", "sure", "okay", "go ahead", "alright"]
    negative_keywords = ["no", "not now", "busy", "later", "can't", "cannot"]
    if any(word in transcript for word in positive_keywords):
        return True
    if any(word in transcript for word in negative_keywords):
        return False
    return False

def process_consent(call_sid, recording_url, transcript):
    collection = get_mongo_collection()
    collection.update_one(
        {"_id": call_sid},
        {"$set": {"consent": {"recording_url": recording_url, "transcript": transcript}}},
        upsert=True
    )
    print(f"[Consent] CallSid: {call_sid}, Recording: {recording_url}, Transcript: {transcript}")

def store_reschedule(call_sid, recording_url):
    # Background transcription for reschedule
    transcript = transcribe_audio(recording_url)
    collection = get_mongo_collection()
    collection.update_one(
        {"_id": call_sid},
        {"$set": {"reschedule": {"recording_url": recording_url, "transcript": transcript}}},
        upsert=True
    )
    print(f"[Reschedule] CallSid: {call_sid}, Recording: {recording_url}, Transcript: {transcript}")

def store_answer(call_sid, q_num, recording_url):
    # Background transcription for answers
    transcript = transcribe_audio(recording_url)
    collection = get_mongo_collection()
    collection.update_one(
        {"_id": call_sid},
        {"$push": {"answers": {"question": q_num, "recording_url": recording_url, "transcript": transcript}}},
        upsert=True
    )
    print(f"[Answer] CallSid: {call_sid}, Q{q_num}: {recording_url}, Transcript: {transcript}")

@router.post("/start-call")
async def start_call(request: StartCallRequest):
    # Optionally, you can use 'name' to personalize the flow in the future
    twilio_service.make_call(request.phone)
    return {"status": "Call initiated"}

@router.post("/twilio-webhook")
async def twilio_webhook(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    step = request.query_params.get("step", "consent")
    call_sid = form.get("CallSid")
    recording_url = form.get("RecordingUrl")

    if call_sid not in CALL_STATE:
        CALL_STATE[call_sid] = {"answers": [], "reschedule": None}

    if step == "consent":
        if recording_url:
            # Synchronously transcribe consent
            transcript = transcribe_audio(recording_url)
            process_consent(call_sid, recording_url, transcript)
            if is_positive_consent(transcript):
                return twiml_play_and_record(QUESTIONS[0], next_step="question1")
            else:
                return twiml_play_and_record("reschedule_request.mp3", next_step="reschedule")
        else:
            return twiml_play_and_record("hr_intro.mp3", next_step="consent")
    elif step == "reschedule":
        if recording_url:
            background_tasks.add_task(store_reschedule, call_sid, recording_url)
            return twiml_play("reschedule_reply.mp3")  # Confirm and end call
        else:
            return twiml_play_and_record("reschedule_request.mp3", next_step="reschedule")
    elif step.startswith("question"):
        q_num = int(step.replace("question", ""))
        if recording_url:
            background_tasks.add_task(store_answer, call_sid, q_num, recording_url)
            if q_num < len(QUESTIONS):
                return twiml_play_and_record(QUESTIONS[q_num], next_step=f"question{q_num+1}")
            else:
                return twiml_play("post_interview_reply.mp3")
        else:
            return twiml_play_and_record(QUESTIONS[q_num-1], next_step=f"question{q_num}")
    else:
        return twiml_play("post_interview_reply.mp3")

def twiml_play_and_record(audio_file, next_step):
    action_url = f"/twilio-webhook?step={next_step}"
    return Response(content=f'''
        <Response>
            <Play>{PUBLIC_BASE_URL}/media/{audio_file}</Play>
            <Record action="{action_url}" method="POST" timeout="3" transcribe="false"/>
        </Response>
    ''', media_type="application/xml")

def twiml_play(audio_file):
    return Response(content=f'''
        <Response>
            <Play>{PUBLIC_BASE_URL}/media/{audio_file}</Play>
        </Response>
    ''', media_type="application/xml")