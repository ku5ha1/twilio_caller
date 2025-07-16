import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

def download_twilio_recording(recording_url, max_attempts=5, delay=3):
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    for attempt in range(max_attempts):
        response = requests.get(recording_url, auth=(twilio_sid, twilio_token))
        if response.status_code == 200:
            return response.content
        elif response.status_code == 404:
            print(f"Recording not ready yet (attempt {attempt+1}/{max_attempts}), retrying in {delay}s...")
            time.sleep(delay)
        else:
            response.raise_for_status()
    raise Exception(f"Recording not found after {max_attempts} attempts: {recording_url}")

def transcribe_audio(recording_url):
    # Download from Twilio with retry
    audio_bytes = download_twilio_recording(recording_url)
    # Transcribe with ElevenLabs STT
    api_key = os.getenv("ELEVENLABS_API_KEY")
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {
        "xi-api-key": api_key,
        "Accept": "application/json"
    }
    files = {
        "audio": ("audio.wav", audio_bytes, "audio/wav")
    }
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
    return response.json()["text"]  # Adjust if ElevenLabs response structure differs