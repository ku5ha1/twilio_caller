from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
TWILIO_WEBHOOK_URL = os.getenv('TWILIO_WEBHOOK_URL', 'https://limitation-must-gba-ce.trycloudflare.com/twilio-webhook')
HR_INTRO_AUDIO_URL = os.getenv('HR_INTRO_AUDIO_URL')

if not TWILIO_PHONE_NUMBER:
    raise ValueError('TWILIO_PHONE_NUMBER not found')

def make_call(phone_number):
    try:
        call = client.calls.create(
            url=TWILIO_WEBHOOK_URL,
            to=phone_number,
            from_=str(TWILIO_PHONE_NUMBER)
        )
        print(f"Call SID: {call.sid}")
        return call.sid
    except Exception as e:
        print(f"Twilio call error: {e}")
        return None

def handle_incoming_call(record_action_url=None):
    response = VoiceResponse()
    # First message from cloned HR voice
    response.play(HR_INTRO_AUDIO_URL)  # Pre-recorded intro
    # Record candidate's reply, send to action URL for further processing
    response.record(
        timeout=10,
        action=record_action_url or (TWILIO_WEBHOOK_URL + "/recording"),
        transcribe=False  # We'll use AssemblyAI for transcription
    )
    return str(response)