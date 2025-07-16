import os
from dotenv import load_dotenv
from pydub import AudioSegment
import io
from elevenlabs.client import ElevenLabs
import requests

load_dotenv()

elevenlabs = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)

def download_twilio_recording(recording_url, max_attempts=5, delay=3):
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    for attempt in range(max_attempts):
        response = requests.get(recording_url, auth=(twilio_sid, twilio_token))
        if response.status_code == 200:
            return response.content
        elif response.status_code == 404:
            print(f"Recording not ready yet (attempt {attempt+1}/{max_attempts}), retrying in {delay}s...")
            import time
            time.sleep(delay)
        else:
            response.raise_for_status()
    raise Exception(f"Recording not found after {max_attempts} attempts: {recording_url}")

def convert_to_mp3(audio_bytes):
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1)
    mp3_io = io.BytesIO()
    audio.export(mp3_io, format="mp3")
    mp3_io.seek(0)
    return mp3_io

def transcribe_audio(recording_url):
    audio_bytes = download_twilio_recording(recording_url)
    mp3_io = convert_to_mp3(audio_bytes)
    transcription = elevenlabs.speech_to_text.convert(
        file=mp3_io,
        model_id="scribe_v1",
        tag_audio_events=True,
        language_code="eng",
        diarize=True,
    )
    # Only return the plain text transcript for MongoDB
    if isinstance(transcription, dict):
        return transcription.get("text", "")
    if hasattr(transcription, "text"):
        return transcription.text
    return str(transcription)