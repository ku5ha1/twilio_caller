from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.gpt_client import GptClient
from app.elevenlabs_client import ElevenLabsClient

router = APIRouter()
gpt_client = GptClient()
elevenlabs_client = ElevenLabsClient()

class ScriptRequest(BaseModel):
    topic: str

class AudioResponse(BaseModel):
    audio_url: str

@router.post("/generate-video-assets/", response_model=AudioResponse)
async def generate_video_assets_endpoint(script_request: ScriptRequest):
    try:
        # Step 1: Generate script
        script = await gpt_client.generate_script(script_request.topic)
        print(f"Generated Script: {script}")

        # Step 2: Generate audio from script
        audio_data = await elevenlabs_client.generate_audio(script)

        # Step 3: Save audio file
        filename_safe_topic = script_request.topic.replace(" ", "_").lower()
        audio_file_path = f"{filename_safe_topic}.mp3"

        with open(audio_file_path, "wb") as f:
            f.write(audio_data)
        print(f"Audio saved to: {audio_file_path}")

        # Step 4: Return URL to access audio
        return {"audio_url": f"/audio/{audio_file_path}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))