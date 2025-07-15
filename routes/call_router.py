from fastapi import APIRouter, Request, Response, BackgroundTasks
from urllib.parse import urlencode
from pydantic import BaseModel
from services import twilio_service
from dotenv import load_dotenv
import os

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
            # Process consent in background
            background_tasks.add_task(process_consent, call_sid, recording_url)
            if is_positive_consent(recording_url):
                return twiml_play_and_record(QUESTIONS[0], next_step="question1")
            else:
                return twiml_play_and_record("reschedule_request.mp3", next_step="reschedule")
        else:
            return twiml_play_and_record("hr_intro.mp3", next_step="consent")
    elif step == "reschedule":
        if recording_url:
            background_tasks.add_task(store_reschedule, call_sid, recording_url)
            return twiml_play("reschedule_reply.mp3")
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
            <Play>https://limitation-must-gba-ce.trycloudflare.com/media/{audio_file}</Play>
            <Record action="{action_url}" method="POST" timeout="3" transcribe="false"/>
        </Response>
    ''', media_type="application/xml")

def twiml_play(audio_file):
    return Response(content=f'''
        <Response>
            <Play>https://limitation-must-gba-ce.trycloudflare.com/media/{audio_file}</Play>
        </Response>
    ''', media_type="application/xml")

def is_positive_consent(recording_url):
    # TODO: Implement keyword or LLM-based consent check
    return True

def process_consent(call_sid, recording_url):
    # Placeholder for consent processing (e.g., transcription, logging)
    print(f"[Consent] CallSid: {call_sid}, Recording: {recording_url}")

def store_reschedule(call_sid, recording_url):
    CALL_STATE[call_sid]["reschedule"] = recording_url
    print(f"[Reschedule] CallSid: {call_sid}, Recording: {recording_url}")

def store_answer(call_sid, q_num, recording_url):
    CALL_STATE[call_sid]["answers"].append(recording_url)
    print(f"[Answer] CallSid: {call_sid}, Q{q_num}: {recording_url}")