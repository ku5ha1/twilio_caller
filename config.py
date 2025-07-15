import os
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hr_calls.db")
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
TELNYX_PHONE_NUMBER = os.getenv("TELNYX_PHONE_NUMBER") 
TWILIO_WEBHOOK_URL = os.getenv("TWILIO_WEBHOOK_URL")

print(TWILIO_WEBHOOK_URL)