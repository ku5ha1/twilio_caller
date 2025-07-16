from fastapi import APIRouter, Request, Response, BackgroundTasks, Form
from urllib.parse import urlencode
from pydantic import BaseModel
from services import twilio_service, assemblyai_service
from dotenv import load_dotenv
import os
from utils.db_utils import get_mongo_collection
from services.assemblyai_service import transcribe_audio
from services.openai_service import analyze_consent
from twilio.twiml.voice_response import VoiceResponse

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

MAX_CONSENT_ATTEMPTS = 3

@router.post("/twilio-webhook")
async def twilio_webhook(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    step = request.query_params.get("step", "consent")
    call_sid = form.get("CallSid")
    consent_attempts = int(form.get("consent_attempts", 0))

    if call_sid not in CALL_STATE:
        CALL_STATE[call_sid] = {"answers": [], "reschedule": None, "consent_attempts": 0}

    if step == "consent":
        # Use <Gather input="speech"> for consent
        action_url = f"{PUBLIC_BASE_URL}/twilio-webhook/consent-speech?call_sid={call_sid}&attempts=0"
        return Response(content=f'''
            <Response>
                <Play>{PUBLIC_BASE_URL}/media/HR_intro_voice.mp3</Play>
                <Gather input="speech" action="{action_url}" method="POST" timeout="5">
                    <Say>Do you consent to proceed with this interview? Please say yes or no.</Say>
                </Gather>
            </Response>
        ''', media_type="application/xml")
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

@router.post("/twilio-webhook/consent-speech")
async def consent_speech(request: Request, call_sid: str = None, attempts: int = 0):
    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    call_sid = call_sid or form.get("CallSid")
    attempts = int(attempts)
    collection = get_mongo_collection()

    # Analyze consent intent using LLM
    llm_result = analyze_consent(speech_result)
    intent = "affirmative" if llm_result.get("proceed") else "negative"
    # Heuristic for reschedule/unclear
    if any(word in speech_result.lower() for word in ["reschedule", "another time", "later"]):
        intent = "reschedule"
    elif not llm_result.get("proceed") and not any(word in speech_result.lower() for word in ["no", "not", "never"]):
        intent = "unclear"

    # Store transcript and LLM result
    collection.update_one(
        {"_id": call_sid},
        {"$set": {"consent": {"transcript": speech_result, "llm_result": llm_result, "attempts": attempts}}},
        upsert=True
    )

    response = VoiceResponse()
    if intent == "affirmative":
        # Proceed to first question
        response.play(f"{PUBLIC_BASE_URL}/media/{QUESTIONS[0]}")
        response.record(action=f"/twilio-webhook?step=question1", method="POST", timeout=2, transcribe="false")
    elif intent == "negative":
        response.play(f"{PUBLIC_BASE_URL}/media/negative_consent.mp3")
        response.hangup()
    elif intent == "reschedule":
        response.play(f"{PUBLIC_BASE_URL}/media/reschedule_request.mp3")
        response.record(action=f"/twilio-webhook?step=reschedule", method="POST", timeout=2, transcribe="false")
    else:  # unclear
        attempts += 1
        if attempts >= MAX_CONSENT_ATTEMPTS:
            response.play(f"{PUBLIC_BASE_URL}/media/negative_consent.mp3")
            response.hangup()
        else:
            response.play(f"{PUBLIC_BASE_URL}/media/unclear_response.mp3")
            gather_url = f"{PUBLIC_BASE_URL}/twilio-webhook/consent-speech?call_sid={call_sid}&attempts={attempts}"
            response.gather(input="speech", action=gather_url, method="POST", timeout=5).say("Do you consent to proceed with this interview? Please say yes or no.")
    return Response(content=str(response), media_type="application/xml")

def twiml_play_and_record(audio_file, next_step):
    action_url = f"/twilio-webhook?step={next_step}"
    return Response(content=f'''
        <Response>
            <Play>{PUBLIC_BASE_URL}/media/{audio_file}</Play>
            <Record action="{action_url}" method="POST" timeout="2" transcribe="false"/>
        </Response>
    ''', media_type="application/xml")

def twiml_play(audio_file):
    return Response(content=f'''
        <Response>
            <Play>{PUBLIC_BASE_URL}/media/{audio_file}</Play>
        </Response>
    ''', media_type="application/xml")
