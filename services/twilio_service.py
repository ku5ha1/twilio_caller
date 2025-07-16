from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import os
from dotenv import load_dotenv

load_dotenv()

client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL')
if not (TWILIO_PHONE_NUMBER and PUBLIC_BASE_URL):
    raise ValueError('TWILIO_PHONE_NUMBER and PUBLIC_BASE_URL must be set in .env')

TWILIO_WEBHOOK_URL = f"{PUBLIC_BASE_URL}/twilio-webhook"
HR_INTRO_AUDIO_URL = os.getenv('HR_INTRO_AUDIO_URL', f"{PUBLIC_BASE_URL}/media/HR_intro_voice.mp3")

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
    response.play(HR_INTRO_AUDIO_URL)
    response.record(
        timeout=10,
        action=record_action_url or f"{TWILIO_WEBHOOK_URL}/recording",
        transcribe=False
    )
    return str(response)