from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
import os
from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, PLIVO_PHONE_NUMBER
import plivo
from plivo import plivoxml

app = FastAPI()

PLIVO_PHONE_NUMBER = os.getenv("PLIVO_PHONE_NUMBER")
if not PLIVO_PHONE_NUMBER:
    raise ValueError('Phone number not found')

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/call/start")
def start_call(phone: str):
    """Trigger an outbound call to the given phone number using Plivo."""
    client = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)
    answer_url = os.getenv("PLIVO_ANSWER_URL", "https://your-server.com/plivo/answer")
    try:
        response = client.calls.create(
            from_=PLIVO_PHONE_NUMBER,
            to_=phone,
            answer_url=answer_url,
            answer_method="POST"
        )
        return JSONResponse({"status": "initiated", "call_uuid": response["request_uuid"]})
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)

@app.post("/plivo/answer")
async def plivo_answer(request: Request):
    response = plivoxml.ResponseElement()
    response.add(
        plivoxml.SpeakElement("Hello, this is the automated HR interview system. Please wait while we begin your interview.")
    )
    # Record the answer and send to /plivo/record
    response.add(
        plivoxml.RecordElement(action="https://your-server.com/plivo/record", method="POST")
    )
    return Response(content=response.to_string(), media_type="application/xml") 