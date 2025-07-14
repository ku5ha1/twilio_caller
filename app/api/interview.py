from fastapi import APIRouter, Depends, HTTPException, Body, Request
from sqlalchemy.orm import Session
from app.models import Candidate, Call, Question, Answer
from app.schemas import AnswerCreate
from app.dependencies import get_db
from typing import Optional, List, Tuple
import datetime
import os
import requests
import logging
from fastapi.responses import JSONResponse
from dateutil import parser as date_parser
import json
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from fastapi import Response
from urllib.parse import urlparse

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")


def query_llm(messages, model="gpt-3.5-turbo", temperature=0.7):
    """
    Query the OpenAI Chat API with a list of messages (conversation history).
    Returns the assistant's reply as a string.
    """
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


# --- HR Bot Prompt Engineering ---

def get_hr_bot_system_prompt(candidate_name, questions):
    return (
        f"You are an automated HR interviewer named DigiBot. Greet the candidate by name (e.g., 'Hello {candidate_name}, this is Sanskriti from Digi9, Bangalore.'). "
        "Ask if it's a good time to talk. If yes, proceed to ask the following questions, one by one, in order. "
        "Do not ask any questions not in this list. After all questions are answered, thank the candidate and end the interview. "
        f"Here are the questions: {' | '.join(questions)}"
    )


def build_conversation_history(system_prompt, qa_pairs):
    """
    Builds the conversation history for the LLM API.
    system_prompt: str
    qa_pairs: list of (question, answer) tuples
    Returns: list of message dicts for OpenAI API
    """
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    for q, a in qa_pairs:
        messages.append({"role": "assistant", "content": q})
        if a:
            messages.append({"role": "user", "content": a})
    return messages

# --- Example Usage: LLM-driven next question ---
def get_next_question_from_llm(qa_pairs, role="Software Engineer"):
    """
    Given the conversation so far, ask the LLM what the next question should be.
    """
    system_prompt = get_hr_bot_system_prompt() + f" The candidate is applying for the role: {role}. "
    messages = build_conversation_history(system_prompt, qa_pairs)
    # Add a final instruction to the LLM
    messages.append({
        "role": "system",
        "content": "Based on the previous answers, what is the most relevant next interview question? Respond with only the question text."
    })
    return query_llm(messages)


@router.post("/interview/start")
def start_interview(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    # Create a new call/interview session
    call = Call(candidate_id=candidate_id, status="in_progress")
    db.add(call)
    db.commit()
    db.refresh(call)
    # Get first question for the candidate's role, ordered by 'order'
    question = db.query(Question).filter(Question.role == candidate.role).order_by(Question.order).first()
    if not question:
        raise HTTPException(status_code=404, detail="No questions found for this role")
    return {"call_id": call.id, "question": {"id": question.id, "text": question.text, "order": question.order}}

@router.post("/interview/next")
def next_question(call_id: int, question_id: int, audio_url: Optional[str] = None, transcript: Optional[str] = None, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    # Store the answer
    answer = Answer(call_id=call_id, question_id=question_id, audio_url=audio_url, transcript=transcript)
    db.add(answer)
    db.commit()
    # Find the next question for this role
    current_question = db.query(Question).filter(Question.id == question_id).first()
    if not current_question:
        raise HTTPException(status_code=404, detail="Question not found")
    next_q = db.query(Question).filter(
        Question.role == current_question.role,
        Question.order > current_question.order
    ).order_by(Question.order).first()
    if next_q:
        return {"next_question": {"id": next_q.id, "text": next_q.text, "order": next_q.order}}
    else:
        # No more questions, mark call as completed
        call.status = "completed"
        call.completed_at = datetime.datetime.utcnow()
        db.commit()
        return {"detail": "Interview complete"}

@router.post("/interview/finish")
def finish_interview(call_id: int, db: Session = Depends(get_db)):
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    call.status = "completed"
    call.completed_at = datetime.datetime.utcnow()
    db.commit()
    return {"detail": "Interview marked as complete"}

@router.post("/llm/next-question")
def llm_next_question(
    qa_pairs: List[Tuple[str, str]] = Body(..., example=[["What is your name?", "John"], ["What is your experience?", "5 years"]]),
    role: str = Body("Software Engineer")
):
    """
    Returns the next interview question as generated by the LLM, given the conversation so far.
    """
    try:
        next_question = get_next_question_from_llm(qa_pairs, role)
        return {"next_question": next_question}
    except Exception as e:
        return {"error": str(e)}


from app.models import Candidate, Call, Question
from sqlalchemy.orm import Session
from voice_generator import generate_speech


@router.post("/twilio/webhook")
async def twilio_webhook(request: Request, db: Session = Depends(get_db)):
    import logging
    try:
        form = await request.form()
        logging.info(f"Incoming /twilio/webhook form data: {dict(form)}")
        call_sid = form.get("CallSid")
        from_number = form.get("From")
        to_number = form.get("To")
        print(f"to_number: {to_number}")
        speech_result = form.get("SpeechResult")
        digits = form.get("Digits")
        call_status = form.get("CallStatus")
        event = form.get("Event")
        logging.info(f"Webhook vars: call_sid={call_sid}, from={from_number}, to={to_number}, speech_result={speech_result}, digits={digits}, call_status={call_status}, event={event}")

        candidate = db.query(Candidate).filter(Candidate.phone == to_number).first()
        if not candidate:
            logging.warning(f"Candidate not found for phone: {to_number}")
            response = VoiceResponse()
            response.say("Sorry, candidate not found. Goodbye.")
            response.hangup()
            return Response(content=str(response), media_type="application/xml")
        call = db.query(Call).filter(Call.candidate_id == candidate.id, Call.status == "in_progress").order_by(Call.started_at.desc()).first()
        if not call:
            logging.warning(f"Call not found for candidate_id: {candidate.id}")
            response = VoiceResponse()
            response.say("Sorry, call not found. Goodbye.")
            response.hangup()
            return Response(content=str(response), media_type="application/xml")

        response = VoiceResponse()
        all_questions = db.query(Question).filter(Question.role == candidate.role).order_by(Question.order).all()
        question_texts = [q.text for q in all_questions]
        # Separate consent from question answers
        answers = call.answers
        consent_given = False
        question_answers = []
        if answers:
            consent_answer = answers[0].transcript.strip().lower() if answers[0].transcript else ""
            consent_given = consent_answer in ["yes", "yeah", "yep", "sure", "ok", "okay"]
            question_answers = answers[1:]
        logging.info(f"answers count: {len(answers) if answers else 0}, consent_given: {consent_given}, question_answers: {len(question_answers)}")
        # If this is the start or after an answer
        if (call_status == "in-progress" and not speech_result and not digits) or speech_result:
            logging.info(f"Processing answer: speech_result={speech_result}")
            # Save answer if present
            if speech_result:
                # If no answers yet, this is consent
                if not answers:
                    answer = Answer(call_id=call.id, question_id=None, transcript=speech_result)
                    db.add(answer)
                    db.commit()
                # If consent already given, save as question answer
                elif consent_given and len(question_answers) < len(question_texts):
                    q_idx = len(question_answers)
                    question = all_questions[q_idx]
                    answer = Answer(call_id=call.id, question_id=question.id, transcript=speech_result)
                    db.add(answer)
                    db.commit()
                    question_answers.append(answer)
            # If no questions, end
            if not question_texts:
                logging.info("No questions found for candidate role.")
                response.say("No questions found for your role. Goodbye.")
                response.hangup()
                return Response(content=str(response), media_type="application/xml")
            # If at start, ask for consent
            if not answers:
                logging.info("At start: asking for consent.")
                system_prompt = get_hr_bot_system_prompt(candidate.name, question_texts)
                messages = build_conversation_history(system_prompt, [])
                messages.append({
                    "role": "system",
                    "content": "Start the interview by greeting the candidate by name and asking if it's a good time to talk. Wait for a yes/no answer."
                })
                llm_response = query_llm(messages)
                audio_filename = f"llm_message_{len(answers)+1}_tts.mp3"
                audio_path = f"media/{audio_filename}"
                if not os.path.exists(audio_path):
                    generate_speech(llm_response, audio_path)
                TWILIO_WEBHOOK_URL = os.environ["TWILIO_WEBHOOK_URL"]
                TWILIO_BASE_URL = TWILIO_WEBHOOK_URL.split("/twilio/webhook")[0]
                gather = Gather(
                    input="speech dtmf",
                    timeout=5,
                    speechTimeout="auto",
                    action=TWILIO_WEBHOOK_URL,
                    method="POST"
                )
                gather.play(f"{TWILIO_BASE_URL}/{audio_path}")
                response.append(gather)
                return Response(content=str(response), media_type="application/xml")
            # If waiting for consent
            elif answers and not consent_given:
                logging.info(f"Waiting for consent, got: {answers[0].transcript if answers else None}")
                # Check if user said yes
                if answers[0].transcript.strip().lower() in ["yes", "yeah", "yep", "sure", "ok", "okay"]:
                    # Ask first question
                    question = question_texts[0]
                    audio_filename = f"llm_message_{len(answers)+1}_tts.mp3"
                    audio_path = f"media/{audio_filename}"
                    if not os.path.exists(audio_path):
                        generate_speech(question, audio_path)
                    TWILIO_WEBHOOK_URL = os.environ["TWILIO_WEBHOOK_URL"]
                    TWILIO_BASE_URL = TWILIO_WEBHOOK_URL.split("/twilio/webhook")[0]
                    gather = Gather(
                        input="speech dtmf",
                        timeout=5,
                        speechTimeout="auto",
                        action=TWILIO_WEBHOOK_URL,
                        method="POST"
                    )
                    gather.play(f"{TWILIO_BASE_URL}/{audio_path}")
                    response.append(gather)
                    return Response(content=str(response), media_type="application/xml")
                else:
                    response.say("Thank you. We will reach out another time. Goodbye.")
                    response.hangup()
                    call.status = "completed"
                    call.completed_at = datetime.datetime.utcnow()
                    db.commit()
                    return Response(content=str(response), media_type="application/xml")
            # If in the middle of questions
            elif consent_given and len(question_answers) < len(question_texts):
                logging.info(f"Asking question {len(question_answers)}: {question_texts[len(question_answers)]}")
                q_idx = len(question_answers)
                question = question_texts[q_idx]
                audio_filename = f"llm_message_{len(answers)+1}_tts.mp3"
                audio_path = f"media/{audio_filename}"
                if not os.path.exists(audio_path):
                    generate_speech(question, audio_path)
                TWILIO_WEBHOOK_URL = os.environ["TWILIO_WEBHOOK_URL"]
                TWILIO_BASE_URL = TWILIO_WEBHOOK_URL.split("/twilio/webhook")[0]
                gather = Gather(
                    input="speech dtmf",
                    timeout=5,
                    speechTimeout="auto",
                    action=TWILIO_WEBHOOK_URL,
                    method="POST"
                )
                gather.play(f"{TWILIO_BASE_URL}/{audio_path}")
                response.append(gather)
                return Response(content=str(response), media_type="application/xml")
            # If all questions answered
            elif consent_given and len(question_answers) >= len(question_texts):
                logging.info("All questions answered, ending interview.")
                system_prompt = get_hr_bot_system_prompt(candidate.name, question_texts)
                messages = build_conversation_history(system_prompt, [(q.text, a.transcript) for q, a in zip(all_questions, question_answers)])
                messages.append({
                    "role": "system",
                    "content": "Thank the candidate and end the interview."
                })
                llm_response = query_llm(messages)
                audio_filename = f"llm_message_{len(answers)+1}_tts.mp3"
                audio_path = f"media/{audio_filename}"
                if not os.path.exists(audio_path):
                    generate_speech(llm_response, audio_path)
                TWILIO_WEBHOOK_URL = os.environ["TWILIO_WEBHOOK_URL"]
                TWILIO_BASE_URL = TWILIO_WEBHOOK_URL.split("/twilio/webhook")[0]
                response.play(f"{TWILIO_BASE_URL}/{audio_path}")
                response.hangup()
                call.status = "completed"
                call.completed_at = datetime.datetime.utcnow()
                db.commit()
                return Response(content=str(response), media_type="application/xml")
        # Default: hang up
        logging.info("Default: hanging up.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logging.error(f"Webhook error: {e}", exc_info=True)
        response = VoiceResponse()
        response.say("An unexpected error occurred. Goodbye.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

@router.post("/twilio/call")
def initiate_twilio_call(candidate_id: int, db: Session = Depends(get_db)):
    """
    Initiate an outbound call to a candidate using the Twilio Voice API.
    """
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "YOUR_TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "YOUR_TWILIO_PHONE_NUMBER")
    TWILIO_WEBHOOK_URL = os.environ["TWILIO_WEBHOOK_URL"]  # Will raise KeyError if not set
    TWILIO_BASE_URL = TWILIO_WEBHOOK_URL.split("/twilio/webhook")[0]

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return JSONResponse(status_code=404, content={"error": "Candidate not found"})
    to_number = candidate.phone

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    import logging
    logging.info(f"Using TWILIO_WEBHOOK_URL: {TWILIO_WEBHOOK_URL}")
    try:
        call = client.calls.create(
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            url=TWILIO_WEBHOOK_URL
        )
        logging.info(f"Twilio call initiation response: {call.sid}")
        # Optionally, store call.sid in DB for tracking
        return {"status": "call_initiated", "call_sid": call.sid}
    except Exception as e:
        logging.error(f"Failed to initiate Twilio call: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)}) 