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

def download_twilio_recording(recording_url, max_attempts=8, delay=3):
    import time
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    min_size = 1000  # bytes, arbitrary minimum for valid audio
    for attempt in range(max_attempts):
        response = requests.get(recording_url, auth=(twilio_sid, twilio_token))
        content_type = response.headers.get('Content-Type', '')
        content_length = int(response.headers.get('Content-Length', '0'))
        print(f"[Download Attempt {attempt+1}] Status: {response.status_code}, Type: {content_type}, Size: {content_length}")
        if response.status_code == 200 and content_type.startswith('audio') and content_length > min_size:
            return response.content
        elif response.status_code == 404 or content_length <= min_size:
            print(f"Recording not ready or too small (attempt {attempt+1}/{max_attempts}), retrying in {delay}s...")
            time.sleep(delay)
        else:
            response.raise_for_status()
    raise Exception(f"Recording not available or invalid after {max_attempts} attempts: {recording_url}")

def convert_to_mp3(audio_bytes):
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1)
    mp3_io = io.BytesIO()
    audio.export(mp3_io, format="mp3")
    mp3_io.seek(0)
    return mp3_io

def transcribe_audio(recording_url):
    audio_bytes = download_twilio_recording(recording_url)
    print(f"[Transcription] Downloaded audio size: {len(audio_bytes)} bytes")
    mp3_io = convert_to_mp3(audio_bytes)
    try:
        transcription = elevenlabs.speech_to_text.convert(
            file=mp3_io,
            model_id="scribe_v1",
            tag_audio_events=True,
            language_code="eng",
            diarize=True,
        )
    except Exception as e:
        print(f"[Transcription Error] ElevenLabs API error: {e}")
        return "[Transcription failed: invalid or unplayable audio]"
    # Only return the plain text transcript for MongoDB
    if isinstance(transcription, dict):
        return transcription.get("text", "")
    if hasattr(transcription, "text"):
        return transcription.text
    return str(transcription)