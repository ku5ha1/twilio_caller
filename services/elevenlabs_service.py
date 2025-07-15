import requests
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

def generate_audio(text: str, voice_id: str = "hr_voice"):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": os.getenv("ELEVENLABS_API_KEY")
    }
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1"
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code != 200:
        raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")
    audio_path = f"audio_{uuid.uuid4().hex}.mp3"
    with open(audio_path, "wb") as f:
        f.write(response.content)
    return audio_path