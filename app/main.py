import os
import json
import logging
from datetime import datetime
from fastapi import FastAPI, Request, Body
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from voice_generator import generate_speech
from dotenv import load_dotenv
import re

os.makedirs(os.path.dirname(output_path), exist_ok=True)

load_dotenv()

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('interview_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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


def validate_environment():
    """Validate all required environment variables are set"""
    required_vars = [
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
        "TWILIO_WEBHOOK_URL", "OPENAI_API_KEY", "OPENAI_API_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise ValueError(f"Missing required environment variables: {missing_vars}")
    
    logger.info("All required environment variables are set")


def query_llm(messages, model="gpt-3.5-turbo", temperature=0.7):
    """Query LLM with enhanced error handling and logging"""
    try:
        import requests
        
        logger.info(f"Querying LLM with model: {model}, temperature: {temperature}")
        logger.debug(f"Messages: {messages}")
        
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        if not OPENAI_API_URL:
            logger.error("OPENAI_API_URL environment variable is not set")
            raise ValueError("OPENAI_API_URL environment variable is not set.")
        
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            logger.info(f"LLM response received successfully: {result[:100]}...")
            return result
        else:
            logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
            raise Exception(f"OpenAI API error: {response.status_code} {response.text}")
            
    except requests.RequestException as e:
        logger.error(f"Request error when querying LLM: {str(e)}")
        raise Exception(f"Request error when querying LLM: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error when querying LLM: {str(e)}")
        raise


def llm_judge_consent(user_response):
    """Judge if user gave consent with enhanced logging"""
    try:
        logger.info(f"Judging consent for response: '{user_response}'")
        
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
        consent_given = result.strip().lower().startswith("yes")
        
        logger.info(f"Consent judgment: {consent_given} (LLM response: '{result}')")
        return consent_given
        
    except Exception as e:
        logger.error(f"Error judging consent: {str(e)}")
        # Default to no consent in case of error
        return False


def load_candidate_data(candidate_id):
    """Load candidate data with error handling"""
    answers_file = f"media/answers_{candidate_id}.json"
    try:
        with open(answers_file, "r") as f:
            data = json.load(f)
        logger.info(f"Loaded existing data for candidate {candidate_id}")
        return data
    except FileNotFoundError:
        logger.info(f"No existing data found for candidate {candidate_id}, creating new")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {answers_file}: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Error loading candidate data: {str(e)}")
        return {}


def save_candidate_data(candidate_id, data):
    """Save candidate data with error handling"""
    answers_file = f"media/answers_{candidate_id}.json"
    try:
        # Ensure media directory exists
        os.makedirs("media", exist_ok=True)
        
        # Add timestamp to data
        data["last_updated"] = datetime.now().isoformat()
        
        with open(answers_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved data for candidate {candidate_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving candidate data: {str(e)}")
        return False


def get_interview_state(candidate_data):
    """Get current interview state"""
    consent_given = candidate_data.get("consent", False)
    
    # Count answered questions (Q1, Q2, etc.)
    answered_questions = [k for k in candidate_data.keys() if k.startswith("Q") and k[1:].isdigit()]
    answered_count = len(answered_questions)
    
    logger.info(f"Interview state - Consent: {consent_given}, Answered: {answered_count}")
    
    return consent_given, answered_count


def generate_audio_if_needed(text, filename):
    """Generate audio file if it doesn't exist"""
    try:
        if not os.path.exists(filename):
            logger.info(f"Generating audio file: {filename}")
            generate_speech(text, filename)
        else:
            logger.info(f"Audio file already exists: {filename}")
        return True
    except Exception as e:
        logger.error(f"Error generating audio file {filename}: {str(e)}")
        return False


def normalize_candidate_id(candidate_id: str) -> str:
    """Normalize candidate ID by removing + and -"""
    return candidate_id.replace("+", "").replace("-", "")

def sanitize_candidate_name(name: str) -> str:
    """Sanitize candidate name for logs and filenames (alphanumeric and spaces only)"""
    return re.sub(r'[^a-zA-Z0-9 ]', '', name)


class CallRequest(BaseModel):
    candidate_name: str
    candidate_number: str


@app.post("/test-call")
def test_call():
    """Simple test endpoint with hardcoded values"""
    try:
        # Hardcoded test values - modify these for your testing
        test_candidate_name = "John Doe"
        test_candidate_number = "+1234567890"  # Replace with your actual test number
        
        logger.info(f"TEST: Initiating test call to {test_candidate_name} at {test_candidate_number}")
        
        validate_environment()
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        call = client.calls.create(
            to=test_candidate_number,
            from_=TWILIO_PHONE_NUMBER,
            url=TWILIO_WEBHOOK_URL + f"?candidate_name={test_candidate_name}"
        )
        
        logger.info(f"TEST: Call initiated successfully. Call SID: {call.sid}")
        return {
            "status": "test_call_initiated", 
            "call_sid": call.sid,
            "test_candidate_name": test_candidate_name,
            "test_candidate_number": test_candidate_number,
            "message": "Test call initiated with hardcoded values"
        }
        
    except Exception as e:
        logger.error(f"TEST: Error initiating test call: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "message": "Test call failed"})


@app.post("/call")
def initiate_call(req: CallRequest = None):
    """Initiate call with enhanced error handling - supports hardcoded testing"""
    try:
        validate_environment()
        
        # For testing - use hardcoded values if no request body provided
        if req is None:
            candidate_name = "Test Candidate"
            candidate_number = "+1234567890"  # Replace with your test number
            logger.info("Using hardcoded test values for call initiation")
        else:
            candidate_name = sanitize_candidate_name(req.candidate_name)
            candidate_number = req.candidate_number
        
        logger.info(f"Initiating call to {candidate_name} at {candidate_number}")
        
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        normalized_id = normalize_candidate_id(candidate_number)
        call = client.calls.create(
            to=candidate_number,
            from_=TWILIO_PHONE_NUMBER,
            url=TWILIO_WEBHOOK_URL + f"?candidate_name={candidate_name}"
        )
        
        logger.info(f"Call initiated successfully. Call SID: {call.sid}")
        return {
            "status": "call_initiated", 
            "call_sid": call.sid, 
            "candidate_name": candidate_name, 
            "candidate_number": candidate_number,
            "candidate_id": normalized_id
        }
        
    except Exception as e:
        logger.error(f"Error initiating call: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    """Handle Twilio webhook with corrected logic and enhanced logging"""
    try:
        form = await request.form()
        candidate_name = sanitize_candidate_name(request.query_params.get("candidate_name", "Candidate"))
        to_number = form.get("To")
        speech_result = form.get("SpeechResult", "").strip()
        call_status = form.get("CallStatus")
        
        logger.info(f"Webhook received - Candidate: {candidate_name}, To: {to_number}, Status: {call_status}")
        logger.info(f"Speech result: '{speech_result}'")
        
        # Use normalized phone number as candidate ID
        candidate_id = normalize_candidate_id(to_number)
        
        # Load candidate data
        candidate_data = load_candidate_data(candidate_id)
        
        # Get current interview state
        consent_given, answered_count = get_interview_state(candidate_data)
        
        response = VoiceResponse()
        
        # Handle consent phase
        if not consent_given:
            if not speech_result:
                # First call - ask for consent
                logger.info("Asking for consent")
                greet = f"Hello {candidate_name}, this is {HR_NAME} from Digi9, Bangalore. Is this a good time to talk?"
                audio_filename = f"media/consent_{candidate_id}.mp3"
                
                if generate_audio_if_needed(greet, audio_filename):
                    gather = Gather(
                        input="speech dtmf",
                        timeout=10,
                        speechTimeout="auto",
                        action=f"/twilio/webhook?candidate_name={candidate_name}",
                        method="POST"
                    )
                    gather.play(audio_filename)
                    response.append(gather)
                else:
                    gather = Gather(
                        input="speech dtmf",
                        timeout=10,
                        speechTimeout="auto",
                        action=f"/twilio/webhook?candidate_name={candidate_name}",
                        method="POST"
                    )
                    gather.say(greet)
                    response.append(gather)
                    
                return Response(content=str(response), media_type="application/xml")
            else:
                # Process consent response
                logger.info(f"Processing consent response: '{speech_result}'")
                
                if llm_judge_consent(speech_result):
                    candidate_data["consent"] = True
                    candidate_data["consent_response"] = speech_result
                    
                    if save_candidate_data(candidate_id, candidate_data):
                        logger.info("Consent given, proceeding to first question")
                        
                        # Ask first question immediately
                        question = BDE_QUESTIONS[0]
                        audio_filename = f"media/question_1_{candidate_id}.mp3"
                        
                        if generate_audio_if_needed(question, audio_filename):
                            gather = Gather(
                                input="speech dtmf",
                                timeout=15,
                                speechTimeout="auto",
                                action=f"/twilio/webhook?candidate_name={candidate_name}",
                                method="POST"
                            )
                            gather.play(audio_filename)
                            response.append(gather)
                        else:
                            gather = Gather(
                                input="speech dtmf",
                                timeout=15,
                                speechTimeout="auto",
                                action=f"/twilio/webhook?candidate_name={candidate_name}",
                                method="POST"
                            )
                            gather.say(question)
                            response.append(gather)
                        
                        return Response(content=str(response), media_type="application/xml")
                    else:
                        logger.error("Failed to save consent data")
                        response.say("I'm sorry, there was a technical issue. Please try again later.")
                        response.hangup()
                        return Response(content=str(response), media_type="application/xml")
                else:
                    logger.info("Consent not given, ending call")
                    response.say("Thank you for your time. We will reach out at a more convenient time. Goodbye.")
                    response.hangup()
                    return Response(content=str(response), media_type="application/xml")
        
        # Handle interview questions
        else:
            # Save answer if we have speech result
            if speech_result:
                question_num = answered_count + 1
                if question_num <= len(BDE_QUESTIONS):
                    logger.info(f"Saving answer for question {question_num}: '{speech_result}'")
                    candidate_data[f"Q{question_num}"] = speech_result
                    candidate_data[f"Q{question_num}_question"] = BDE_QUESTIONS[question_num - 1]
                    
                    if not save_candidate_data(candidate_id, candidate_data):
                        logger.error("Failed to save answer")
                    
                    answered_count += 1
            
            # Check if we have more questions
            if answered_count < len(BDE_QUESTIONS):
                question_num = answered_count + 1
                question = BDE_QUESTIONS[answered_count]
                audio_filename = f"media/question_{question_num}_{candidate_id}.mp3"
                
                logger.info(f"Asking question {question_num}: '{question}'")
                
                if generate_audio_if_needed(question, audio_filename):
                    gather = Gather(
                        input="speech dtmf",
                        timeout=15,
                        speechTimeout="auto",
                        action=f"/twilio/webhook?candidate_name={candidate_name}",
                        method="POST"
                    )
                    gather.play(audio_filename)
                    response.append(gather)
                else:
                    gather = Gather(
                        input="speech dtmf",
                        timeout=15,
                        speechTimeout="auto",
                        action=f"/twilio/webhook?candidate_name={candidate_name}",
                        method="POST"
                    )
                    gather.say(question)
                    response.append(gather)
                
                return Response(content=str(response), media_type="application/xml")
            else:
                # Interview complete
                logger.info("Interview completed successfully")
                candidate_data["interview_completed"] = True
                candidate_data["completion_time"] = datetime.now().isoformat()
                save_candidate_data(candidate_id, candidate_data)
                
                response.say("Thank you for your time and responses. Our team will review your application and get back to you soon. Have a great day!")
                response.hangup()
                return Response(content=str(response), media_type="application/xml")
    
    except Exception as e:
        logger.error(f"Unexpected error in webhook: {str(e)}")
        response = VoiceResponse()
        response.say("I'm sorry, there was a technical issue. Please try again later.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        validate_environment()
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(status_code=500, content={"status": "unhealthy", "error": str(e)})


@app.get("/test-data/{candidate_id}")
def get_test_data(candidate_id: str):
    """Get test candidate data with enhanced formatting"""
    try:
        data = load_candidate_data(candidate_id)
        if data:
            # Format for better readability during testing
            formatted_data = {
                "candidate_id": candidate_id,
                "consent_given": data.get("consent", False),
                "consent_response": data.get("consent_response", ""),
                "interview_completed": data.get("interview_completed", False),
                "completion_time": data.get("completion_time", ""),
                "last_updated": data.get("last_updated", ""),
                "answers": {}
            }
            
            # Format questions and answers nicely
            for i in range(1, len(BDE_QUESTIONS) + 1):
                question_key = f"Q{i}"
                if question_key in data:
                    formatted_data["answers"][f"Question {i}"] = {
                        "question": BDE_QUESTIONS[i-1],
                        "answer": data[question_key]
                    }
            
            return formatted_data
        else:
            return JSONResponse(status_code=404, content={"error": "Test candidate not found"})
    except Exception as e:
        logger.error(f"Error retrieving test candidate data: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/candidate/{candidate_id}")
def get_candidate_data(candidate_id: str):
    """Get candidate interview data"""
    try:
        normalized_id = normalize_candidate_id(candidate_id)
        data = load_candidate_data(normalized_id)
        if data:
            return data
        else:
            return JSONResponse(status_code=404, content={"error": "Candidate not found"})
    except Exception as e:
        logger.error(f"Error retrieving candidate data: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# NOTE: /test-call and /test-data endpoints are for development/testing only.
# Remove or protect these endpoints before deploying to production.

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Interview Bot application")
    uvicorn.run(app, host="0.0.0.0", port=8000)