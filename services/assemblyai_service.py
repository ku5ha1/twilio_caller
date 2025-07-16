import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

def download_twilio_recording(recording_url):
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    response = requests.get(recording_url, auth=(twilio_sid, twilio_token))
    response.raise_for_status()
    return response.content

def upload_to_assemblyai(audio_bytes):
    headers = {'authorization': os.getenv("ASSEMBLYAI_API_KEY")}
    upload_response = requests.post(
        'https://api.assemblyai.com/v2/upload',
        headers=headers,
        data=audio_bytes
    )
    upload_response.raise_for_status()
    return upload_response.json()['upload_url']

def transcribe_audio(recording_url, poll_interval=3, max_attempts=20):
    # Download from Twilio
    audio_bytes = download_twilio_recording(recording_url)
    # Upload to AssemblyAI
    assemblyai_url = upload_to_assemblyai(audio_bytes)
    # Start transcription
    headers = {
        "authorization": os.getenv("ASSEMBLYAI_API_KEY"),
        "content-type": "application/json"
    }
    data = {"audio_url": assemblyai_url}
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