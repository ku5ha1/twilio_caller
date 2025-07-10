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

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = os.getenv("OPENAI_API_URL")

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "YOUR_TELNYX_API_KEY")
TELNYX_API_BASE = "https://api.telnyx.com/v2"


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

def get_hr_bot_system_prompt():
    """
    Returns the system prompt for the HR interview bot persona.
    """
    return (
        "You are an automated HR interviewer. "
        "You are friendly, professional, and concise. "
        "Your job is to screen candidates for specific roles by asking predefined questions, "
        "extracting key information, and following up for clarification if needed. "
        "Do not answer on behalf of the candidate. Only ask questions or acknowledge their responses. "
        "If a candidate is not a fit, politely end the interview."
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

def telnyx_play_audio(call_control_id, audio_url):
    """
    Play an audio file to the call using Telnyx Call Control API.
    """
    endpoint = f"{TELNYX_API_BASE}/calls/{call_control_id}/actions/playback_start"
    headers = {"Authorization": f"Bearer {TELNYX_API_KEY}", "Content-Type": "application/json"}
    payload = {"audio_url": audio_url}
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logging.info(f"Telnyx play_audio response: {resp.json()}")
        return True
    except Exception as e:
        logging.error(f"Telnyx play_audio failed: {e}")
        return False

def telnyx_start_transcription(call_control_id):
    """
    Start transcription on the call using Telnyx Call Control API.
    """
    endpoint = f"{TELNYX_API_BASE}/calls/{call_control_id}/actions/transcription_start"
    headers = {"Authorization": f"Bearer {TELNYX_API_KEY}", "Content-Type": "application/json"}
    payload = {"language": "en-US"}
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logging.info(f"Telnyx start_transcription response: {resp.json()}")
        return True
    except Exception as e:
        logging.error(f"Telnyx start_transcription failed: {e}")
        return False

def telnyx_hangup_call(call_control_id):
    """
    Hang up the call using Telnyx Call Control API.
    """
    endpoint = f"{TELNYX_API_BASE}/calls/{call_control_id}/actions/hangup"
    headers = {"Authorization": f"Bearer {TELNYX_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(endpoint, headers=headers, timeout=10)
        resp.raise_for_status()
        logging.info(f"Telnyx hangup response: {resp.json()}")
        return True
    except Exception as e:
        logging.error(f"Telnyx hangup failed: {e}")
        return False


@router.post("/telnyx/webhook")
async def telnyx_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        event_type = payload.get("data", {}).get("event_type") or payload.get("event_type")
        logging.info(f"Received Telnyx event: {event_type}")
        logging.info(f"Payload: {payload}")

        if event_type == "call.answered":
            call_control_id = payload["data"]["payload"].get("call_control_id")
            to_number = payload["data"]["payload"].get("to")
            candidate = db.query(Candidate).filter(Candidate.phone == to_number).first()
            if not candidate:
                logging.error(f"No candidate found with phone {to_number}")
                return JSONResponse(status_code=404, content={"error": "Candidate not found"})
            question = db.query(Question).filter(Question.role == candidate.role).order_by(Question.order).first()
            if not question:
                logging.error(f"No questions found for role {candidate.role}")
                return JSONResponse(status_code=404, content={"error": "No questions for role"})
            audio_filename = f"question_{question.id}_tts.mp3"
            audio_path = f"media/{audio_filename}"
            try:
                generate_speech(question.text, audio_path)
            except Exception as e:
                logging.error(f"TTS generation failed: {e}")
                # Fallback: End call or notify admin
                return JSONResponse(status_code=500, content={"error": "TTS failed"})
            public_audio_url = f"https://yourdomain.com/{audio_path}"
            if not telnyx_play_audio(call_control_id, public_audio_url):
                # Fallback: End call or notify admin
                logging.error("Failed to play audio. Consider ending call or notifying admin.")
                return JSONResponse(status_code=500, content={"error": "Failed to play audio"})

        elif event_type == "call.speak.ended":
            call_control_id = payload["data"]["payload"].get("call_control_id")
            if not telnyx_start_transcription(call_control_id):
                logging.error("Failed to start transcription. Consider ending call or notifying admin.")
                return JSONResponse(status_code=500, content={"error": "Failed to start transcription"})

        elif event_type == "call.transcription":
            logging.info("Received candidate's transcribed answer.")
            call_control_id = payload["data"]["payload"].get("call_control_id")
            to_number = payload["data"]["payload"].get("to")
            transcription = payload["data"]["payload"].get("transcription")
            candidate = db.query(Candidate).filter(Candidate.phone == to_number).first()
            if not candidate:
                logging.error(f"No candidate found with phone {to_number}")
                return JSONResponse(status_code=404, content={"error": "Candidate not found"})
            call = db.query(Call).filter(Call.candidate_id == candidate.id, Call.status == "in_progress").order_by(Call.started_at.desc()).first()
            if not call:
                logging.error(f"No in-progress call found for candidate {candidate.id}")
                return JSONResponse(status_code=404, content={"error": "Call not found"})
            # --- Robust intent handling for silence/unclear ---
            unclear_phrases = ["i don't know", "not sure", "no idea", "can't say", "don't understand", "unclear"]
            if not transcription or any(phrase in transcription.lower() for phrase in unclear_phrases):
                # Prompt for clarification or repeat the question
                clarification_prompt = "Sorry, I didn't catch that. Could you please repeat or clarify your answer?"
                audio_filename = f"clarify_{call_control_id}.mp3"
                audio_path = f"media/{audio_filename}"
                try:
                    generate_speech(clarification_prompt, audio_path)
                except Exception as e:
                    logging.error(f"TTS generation for clarification failed: {e}")
                    return JSONResponse(status_code=500, content={"error": "TTS failed for clarification"})
                public_audio_url = f"https://yourdomain.com/{audio_path}"
                if not telnyx_play_audio(call_control_id, public_audio_url):
                    logging.error("Failed to play clarification prompt audio.")
                    return JSONResponse(status_code=500, content={"error": "Failed to play clarification prompt audio"})
                return {"status": "clarification_prompted"}
            # --- LLM-driven decision logic (tuned prompt) ---
            answers = db.query(Answer).filter(Answer.call_id == call.id).order_by(Answer.timestamp).all()
            qa_pairs = []
            for ans in answers:
                q = db.query(Question).filter(Question.id == ans.question_id).first()
                qa_pairs.append((q.text, ans.transcript if ans.transcript else ""))
            last_question = None
            if answers:
                last_question = db.query(Question).filter(Question.id == answers[-1].question_id).first()
            if last_question:
                qa_pairs.append((last_question.text, transcription))
            # Enhanced system prompt for LLM
            system_prompt = (
                "You are an HR interview bot. You must only use the predefined questions provided. "
                "After each candidate answer, decide what to do next. "
                "Respond with a JSON: {\"action\": \"repeat|next|reschedule|end|clarify\", \"message\": \"...\"}. "
                "If the candidate asks for a repeat, set action to 'repeat'. If they want to reschedule, set action to 'reschedule'. "
                "If the answer is unclear, silent, or not understood, set action to 'clarify'. "
                "If the answer is valid, set action to 'next'. If the candidate wants to end, set action to 'end'. "
                "For 'next', use the next question from the provided list."
            )
            messages = [{"role": "system", "content": system_prompt}]
            for q, a in qa_pairs:
                messages.append({"role": "assistant", "content": q})
                if a:
                    messages.append({"role": "user", "content": a})
            all_questions = db.query(Question).filter(Question.role == candidate.role).order_by(Question.order).all()
            asked_ids = [ans.question_id for ans in answers]
            remaining_questions = [q for q in all_questions if q.id not in asked_ids]
            questions_list = [q.text for q in remaining_questions]
            messages.append({"role": "system", "content": f"Remaining questions: {questions_list}"})
            try:
                llm_response = query_llm(messages)
                logging.info(f"LLM decision response: {llm_response}")
                decision = json.loads(llm_response)
                action = decision.get("action")
                next_message = decision.get("message")
            except Exception as e:
                logging.error(f"LLM decision logic failed: {e}")
                return JSONResponse(status_code=500, content={"error": "LLM decision logic failed"})
            # Branch based on LLM action
            if action == "clarify":
                clarification_prompt = next_message or "Sorry, I didn't catch that. Could you please repeat or clarify your answer?"
                audio_filename = f"clarify_{call_control_id}.mp3"
                audio_path = f"media/{audio_filename}"
                try:
                    generate_speech(clarification_prompt, audio_path)
                except Exception as e:
                    logging.error(f"TTS generation for clarification failed: {e}")
                    return JSONResponse(status_code=500, content={"error": "TTS failed for clarification"})
                public_audio_url = f"https://yourdomain.com/{audio_path}"
                if not telnyx_play_audio(call_control_id, public_audio_url):
                    logging.error("Failed to play clarification prompt audio.")
                    return JSONResponse(status_code=500, content={"error": "Failed to play clarification prompt audio"})
                return {"status": "clarification_prompted"}
            elif action == "repeat":
                if last_question:
                    audio_filename = f"question_{last_question.id}_tts.mp3"
                    audio_path = f"media/{audio_filename}"
                    try:
                        generate_speech(last_question.text, audio_path)
                    except Exception as e:
                        logging.error(f"TTS generation failed: {e}")
                        return JSONResponse(status_code=500, content={"error": "TTS failed for repeat"})
                    public_audio_url = f"https://yourdomain.com/{audio_path}"
                    if not telnyx_play_audio(call_control_id, public_audio_url):
                        logging.error("Failed to play repeat question audio.")
                        return JSONResponse(status_code=500, content={"error": "Failed to play repeat question audio"})
                    return {"status": "question_repeated"}
            elif action == "reschedule":
                reschedule_prompt = next_message or "No problem! Please say a preferred date and time for your interview after the beep, or press a key if you prefer to be contacted later. Thank you!"
                audio_filename = f"reschedule_{call_control_id}.mp3"
                audio_path = f"media/{audio_filename}"
                try:
                    generate_speech(reschedule_prompt, audio_path)
                except Exception as e:
                    logging.error(f"TTS generation for reschedule prompt failed: {e}")
                    return JSONResponse(status_code=500, content={"error": "TTS failed for reschedule prompt"})
                public_audio_url = f"https://yourdomain.com/{audio_path}"
                if not telnyx_play_audio(call_control_id, public_audio_url):
                    logging.error("Failed to play reschedule prompt audio.")
                    return JSONResponse(status_code=500, content={"error": "Failed to play reschedule prompt audio"})
                call.status = "rescheduled"
                db.commit()
                return {"status": "reschedule_requested"}
            elif action == "end":
                goodbye_text = next_message or "Thank you for your time. Goodbye!"
                audio_filename = f"goodbye_{call_control_id}.mp3"
                audio_path = f"media/{audio_filename}"
                try:
                    generate_speech(goodbye_text, audio_path)
                except Exception as e:
                    logging.error(f"TTS generation for goodbye failed: {e}")
                    return JSONResponse(status_code=500, content={"error": "TTS failed for goodbye"})
                public_audio_url = f"https://yourdomain.com/{audio_path}"
                telnyx_play_audio(call_control_id, public_audio_url)
                # Hang up the call via Telnyx API
                telnyx_hangup_call(call_control_id)
                call.status = "completed"
                call.completed_at = datetime.datetime.utcnow()
                db.commit()
                return {"status": "call_ended"}
            elif action == "next":
                last_answer = db.query(Answer).filter(Answer.call_id == call.id).order_by(Answer.timestamp.desc()).first()
                if last_answer and last_answer.transcript is None:
                    last_answer.transcript = transcription
                    db.commit()
                if remaining_questions:
                    next_q = remaining_questions[0]
                    audio_filename = f"question_{next_q.id}_tts.mp3"
                    audio_path = f"media/{audio_filename}"
                    try:
                        generate_speech(next_q.text, audio_path)
                    except Exception as e:
                        logging.error(f"TTS generation failed: {e}")
                        return JSONResponse(status_code=500, content={"error": "TTS failed for next question"})
                    public_audio_url = f"https://yourdomain.com/{audio_path}"
                    if not telnyx_play_audio(call_control_id, public_audio_url):
                        logging.error("Failed to play next question audio.")
                        return JSONResponse(status_code=500, content={"error": "Failed to play next question audio"})
                    new_answer = Answer(call_id=call.id, question_id=next_q.id)
                    db.add(new_answer)
                    db.commit()
                    return {"status": "next_question_asked"}
                else:
                    call.status = "completed"
                    call.completed_at = datetime.datetime.utcnow()
                    db.commit()
                    logging.info(f"Interview complete for call {call.id}. Would end call via Telnyx API.")
                    # Hang up the call via Telnyx API
                    telnyx_hangup_call(call_control_id)
                    return {"status": "interview_complete"}
            else:
                logging.warning(f"LLM returned unknown action: {action}")
                return {"status": "unknown_llm_action", "action": action}
            # --- End LLM-driven decision logic ---

        elif event_type == "call.hangup":
            logging.info("Call ended by candidate or system.")
            # Optionally, notify admin or update call status if not already done

        elif event_type == "call.machine.detection.ended":
            # Telnyx AMD event: check if machine or human
            call_control_id = payload["data"]["payload"].get("call_control_id")
            to_number = payload["data"]["payload"].get("to")
            result = payload["data"]["payload"].get("result")  # 'machine' or 'human'
            candidate = db.query(Candidate).filter(Candidate.phone == to_number).first()
            call = db.query(Call).filter(Call.candidate_id == candidate.id, Call.status == "in_progress").order_by(Call.started_at.desc()).first() if candidate else None
            if result == "machine":
                logging.info("Answering machine detected. Playing voicemail message.")
                # Generate TTS for voicemail message
                voicemail_text = "Hello, this is the HR team. We tried to reach you for your interview. Please call us back or await a reschedule. Thank you!"
                audio_filename = f"voicemail_{call_control_id}.mp3"
                audio_path = f"media/{audio_filename}"
                try:
                    generate_speech(voicemail_text, audio_path)
                except Exception as e:
                    logging.error(f"TTS generation for voicemail failed: {e}")
                    return JSONResponse(status_code=500, content={"error": "TTS failed for voicemail"})
                public_audio_url = f"https://yourdomain.com/{audio_path}"
                if not telnyx_play_audio(call_control_id, public_audio_url):
                    logging.error("Failed to play voicemail audio.")
                    return JSONResponse(status_code=500, content={"error": "Failed to play voicemail audio"})
                # Mark call as voicemail in DB
                if call:
                    call.status = "voicemail"
                    db.commit()
                # Optionally, notify HR or schedule retry here
            elif result == "human":
                logging.info("Human detected. Proceeding with normal interview flow.")
            else:
                logging.warning(f"Unknown AMD result: {result}")

        elif event_type == "call.recording.saved":
            # Telnyx event: call recording is available
            call_control_id = payload["data"]["payload"].get("call_control_id")
            to_number = payload["data"]["payload"].get("to")
            recording_url = payload["data"]["payload"].get("recording_urls", [None])[0]  # usually a list
            candidate = db.query(Candidate).filter(Candidate.phone == to_number).first()
            call = db.query(Call).filter(Call.candidate_id == candidate.id, Call.status != None).order_by(Call.started_at.desc()).first() if candidate else None
            if call and recording_url:
                call.call_recording_url = recording_url
                db.commit()
                logging.info(f"Stored call recording URL for call {call.id}: {recording_url}")
                return {"status": "recording_url_saved", "recording_url": recording_url}
            else:
                logging.warning(f"Could not store recording URL. call: {call}, url: {recording_url}")
                return {"status": "recording_url_not_saved"}

        else:
            logging.info(f"Unhandled Telnyx event: {event_type}")

        return {"status": "received", "event_type": event_type}
    except Exception as e:
        logging.error(f"Webhook processing failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)}) 

@router.post("/telnyx/call")
def initiate_telnyx_call(candidate_id: int, db: Session = Depends(get_db)):
    """
    Initiate an outbound call to a candidate using the Telnyx Voice API.
    """
    TELNYX_CONNECTION_ID = os.getenv("TELNYX_CONNECTION_ID", "YOUR_CONNECTION_ID")  # Replace with your real connection ID
    TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "YOUR_TELNYX_API_KEY")
    TELNYX_API_BASE = "https://api.telnyx.com/v2"
    WEBHOOK_URL = os.getenv("TELNYX_WEBHOOK_URL", "https://yourdomain.com/telnyx/webhook")

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return JSONResponse(status_code=404, content={"error": "Candidate not found"})
    to_number = candidate.phone
    from_number = os.getenv("TELNYX_PHONE_NUMBER", "YOUR_TELNYX_NUMBER")

    endpoint = f"{TELNYX_API_BASE}/calls"
    headers = {"Authorization": f"Bearer {TELNYX_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "connection_id": TELNYX_CONNECTION_ID,
        "to": to_number,
        "from": from_number,
        "webhook_url": WEBHOOK_URL
    }
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logging.info(f"Telnyx call initiation response: {data}")
        # Optionally, store call_control_id or call_id in DB for tracking
        return {"status": "call_initiated", "response": data}
    except Exception as e:
        logging.error(f"Failed to initiate Telnyx call: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)}) 