from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.gpt_client import GptClient

router = APIRouter()
gpt_client = GptClient()

class ScriptRequest(BaseModel):
    topic: str

class ScriptResponse(BaseModel):
    script: str

@router.post("/generate-script/", response_model=ScriptResponse)
async def generate_script_endpoint(script_request: ScriptRequest):
    try:
        script = await gpt_client.generate_script(script_request.topic)
        return {"script": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))