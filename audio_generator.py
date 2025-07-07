import os
import requests
from dotenv import load_dotenv

load_dotenv()

class AudioGenerator:
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = "mcXfdl3fJTBW24JkkLwE".strip()
        if not self.api_key or not self.voice_id:
            raise ValueError("ElevenLabs API key or Voice ID not found in .env")

    def generate_audio(self, text, output_file="media/output_audio.mp3"):
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }

        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        print(f"[DEBUG] Using Voice ID: {self.voice_id}")
        print(f"[DEBUG] Request Data: {data}")
        print("[INFO] Generating audio...")
        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Audio generation failed: {response.text}")

        with open(output_file, "wb") as f:
            f.write(response.content)
        
        print(response.content)
        print(f"[SUCCESS] Audio saved to {output_file}")
        return output_file