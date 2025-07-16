import requests
import os
import time
from dotenv import load_dotenv
from pydub import AudioSegment
import io

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

def convert_to_wav(audio_bytes):
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    except Exception:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1)
    wav_io = io.BytesIO()
    audio.export(wav_io, format="wav")
    wav_io.seek(0)
    return wav_io.read()

def transcribe_audio(recording_url):
    # Download from Twilio with retry
    audio_bytes = download_twilio_recording(recording_url)
    wav_bytes = convert_to_wav(audio_bytes)
    # Transcribe with ElevenLabs STT
    api_key = os.getenv("ELEVENLABS_API_KEY")
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {
        "xi-api-key": api_key,
        "Accept": "application/json"
    }
    files = {
        "audio": ("audio.wav", wav_bytes, "audio/wav")
    }
    response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()
    return response.json()["text"]  # Adjust if ElevenLabs response structure differs