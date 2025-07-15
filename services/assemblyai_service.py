import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

def transcribe_audio(audio_url: str, poll_interval=3, max_attempts=20):
    headers = {
        "authorization": os.getenv("ASSEMBLYAI_API_KEY"),
        "content-type": "application/json"
    }
    data = {
        "audio_url": audio_url
    }
    url = "https://api.assemblyai.com/v2/transcript"
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    transcript_id = response.json()['id']

    for attempt in range(max_attempts):
        poll_response = requests.get(f"{url}/{transcript_id}", headers=headers)
        poll_response.raise_for_status()
        status = poll_response.json()['status']
        if status == 'completed':
            return poll_response.json()['text']
        elif status == 'failed':
            raise Exception(f"Transcription failed: {poll_response.json()}")
        time.sleep(poll_interval)
    raise TimeoutError("Transcription polling timed out.")