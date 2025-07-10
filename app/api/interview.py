from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.models import Candidate, Call, Question, Answer
from app.schemas import AnswerCreate
from app.dependencies import get_db
from typing import Optional, List, Tuple
import datetime

router = APIRouter()

import os
import requests

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