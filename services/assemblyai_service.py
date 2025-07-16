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

def convert_audio(audio_bytes, target_format="wav"):
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1)
    out_io = io.BytesIO()
    audio.export(out_io, format=target_format)
    out_io.seek(0)
    return out_io.read()

def transcribe_audio(recording_url):
    audio_bytes = download_twilio_recording(recording_url)
    api_key = os.getenv("ELEVENLABS_API_KEY")
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {
        "xi-api-key": api_key,
        "Accept": "application/json"
    }
    # Try WAV first
    try:
        wav_bytes = convert_audio(audio_bytes, "wav")
        files = {"audio": ("audio.wav", wav_bytes, "audio/wav")}
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()
        return response.json()["text"]
    except Exception as e:
        print(f"WAV failed: {e}, trying MP3...")
        mp3_bytes = convert_audio(audio_bytes, "mp3")
        files = {"audio": ("audio.mp3", mp3_bytes, "audio/mp3")}
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()
        return response.json()["text"]