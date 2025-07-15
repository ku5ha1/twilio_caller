import os
import json
import logging
from fastapi import FastAPI, Request, Body
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from voice_generator import generate_speech
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# HR and Interview Config
HR_NAME = "Sanskriti"
BDE_QUESTIONS = [
    "What is your full name?",
    "What is your current location?",
    "What is your current company and role?",
    "What is your current CTC and expected CTC?",
    "What is your notice period or earliest joining date?",
    "Have you previously worked in a target-driven sales role? Briefly mention your targets and performance.",
    "Do you have experience selling tech products or services? If yes, please describe briefly.",
    "Have you engaged with decision-makers like CTOs, founders, or tech leads in your sales process?",
    "What types of products or services have you sold previously?",
    "Are you comfortable with a Work From Office (WFO) role based in Bangalore?",
    "Do you have a personal laptop you can use for work?",
    "Have you used any sales or CRM tools before? If yes, which ones?"
]

# Twilio config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
TWILIO_WEBHOOK_URL = os.getenv("TWILIO_WEBHOOK_URL")

# LLM config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

def query_llm(messages, model="gpt-3.5-turbo", temperature=0.7):
    import requests
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    else:
        raise Exception(f"OpenAI API error: {response.status_code} {response.text}")

def llm_judge_consent(user_response):
    prompt = (
        f"The candidate was asked if this is a good time to talk. "
        f"Their response was: '{user_response}'. "
        "Should the interview proceed? Reply only with 'yes' or 'no'."
    )
    messages = [
        {"role": "system", "content": "You are an HR assistant."},
        {"role": "user", "content": prompt}
    ]
    result = query_llm(messages)
    return result.strip().lower().startswith("yes")

class CallRequest(BaseModel):
    candidate_name: str
    candidate_number: str

@app.post("/call")
def initiate_call(req: CallRequest):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        call = client.calls.create(
            to=req.candidate_number,
            from_=TWILIO_PHONE_NUMBER,
            url=TWILIO_WEBHOOK_URL + f"?candidate_name={req.candidate_name}"
        )
        return {"status": "call_initiated", "call_sid": call.sid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    form = await request.form()
    candidate_name = request.query_params.get("candidate_name", "Candidate")
    to_number = form.get("To")
    speech_result = form.get("SpeechResult")
    call_status = form.get("CallStatus")
    response = VoiceResponse()
    # Use phone number as candidate ID for now
    candidate_id = to_number
    answers_file = f"media/answers_{candidate_id}.json"
    try:
        with open(answers_file, "r") as f:
            candidate_answers = json.load(f)
    except FileNotFoundError:
        candidate_answers = {}
    answered_count = len([k for k in candidate_answers if k.startswith("Q")])
    consent_given = candidate_answers.get("consent", False)
    # 1. Ask for consent if not given
    if not consent_given:
        if answered_count == 0 and not speech_result:
            greet = f"Hello {candidate_name}, this is {HR_NAME} from Digi9, Bangalore. Is this a good time to talk?"
            audio_filename = f"media/llm_message_consent_{candidate_id}.mp3"
            if not os.path.exists(audio_filename):
                generate_speech(greet, audio_filename)
            gather = Gather(
                input="speech dtmf",
                timeout=5,
                speechTimeout="auto",
                action="/twilio/webhook?candidate_name=" + candidate_name,
                method="POST"
            )
            gather.play(audio_filename)
            response.append(gather)
            return Response(content=str(response), media_type="application/xml")
        elif speech_result:
            if llm_judge_consent(speech_result.strip()):
                candidate_answers["consent"] = True
                with open(answers_file, "w") as f:
                    json.dump(candidate_answers, f)
                question_idx = 0
            else:
                response.say("Thank you. We will reach out another time. Goodbye.")
                response.hangup()
                return Response(content=str(response), media_type="application/xml")
        else:
            gather = Gather(
                input="speech dtmf",
                timeout=5,
                speechTimeout="auto",
                action="/twilio/webhook?candidate_name=" + candidate_name,
                method="POST"
            )
            gather.play(f"media/llm_message_consent_{candidate_id}.mp3")
            response.append(gather)
            return Response(content=str(response), media_type="application/xml")
    else:
        question_idx = answered_count
    # 2. Ask next question or finish
    if question_idx < len(BDE_QUESTIONS):
        if speech_result and consent_given and answered_count > 0:
            prev_q = BDE_QUESTIONS[question_idx - 1]
            candidate_answers[f"Q{question_idx}"] = speech_result
            with open(answers_file, "w") as f:
                json.dump(candidate_answers, f)
        question = BDE_QUESTIONS[question_idx]
        audio_filename = f"media/llm_message_q{question_idx+1}_{candidate_id}.mp3"
        if not os.path.exists(audio_filename):
            generate_speech(question, audio_filename)
        gather = Gather(
            input="speech dtmf",
            timeout=5,
            speechTimeout="auto",
            action="/twilio/webhook?candidate_name=" + candidate_name,
            method="POST"
        )
        gather.play(audio_filename)
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")
    else:
        if speech_result and consent_given and answered_count == len(BDE_QUESTIONS):
            prev_q = BDE_QUESTIONS[-1]
            candidate_answers[f"Q{len(BDE_QUESTIONS)}"] = speech_result
            with open(answers_file, "w") as f:
                json.dump(candidate_answers, f)
        response.say("Thank you for your responses. We will get back to you soon. Goodbye.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml") 