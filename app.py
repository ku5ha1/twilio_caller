from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
import os

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/twilio/voice")
def twilio_voice_webhook(request: Request):
    response = VoiceResponse()
    response.say("Hello, this is the automated HR interview system. Please wait while we begin your interview.")
    return PlainTextResponse(str(response), media_type="application/xml")

@app.post("/call/start")
def start_call(phone: str):
    """Trigger an outbound call to the given phone number using Twilio."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    # Replace with your public ngrok URL or server URL
    webhook_url = os.getenv("TWILIO_WEBHOOK_URL", "http://localhost:8000/twilio/voice")
    try:
        call = client.calls.create(
            to=phone,
            from_=TWILIO_PHONE_NUMBER,
            url=webhook_url
        )
        return JSONResponse({"status": "initiated", "call_sid": call.sid})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500) 