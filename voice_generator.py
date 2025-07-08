import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    print("ELEVENLABS_API_KEY is not set")
    exit(1)
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
if not ELEVENLABS_VOICE_ID:
    print("ELEVENLABS_VOICE_ID is not set")
    exit(1)

ELEVENLABS_TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"


def generate_speech(text, output_path):
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
    response = requests.post(ELEVENLABS_TTS_URL, json=payload, headers=headers)
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path
    else:
        raise Exception(f"TTS failed: {response.status_code} {response.text}") 