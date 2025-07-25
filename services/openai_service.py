from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def analyze_consent(transcript: str):
    prompt = f"""
    Classify the following candidate response as one of: 'affirmative', 'negative', 'reschedule', or 'unclear'.
    Only return a JSON object with an 'intent' key and no explanation.
    
    Transcript: "{transcript}"

    Example response:
    {{ "intent": "affirmative" }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        # Parse the JSON output from the LLM
        result = json.loads(content)
        return result
    except Exception as e:
        # Log or handle the error as needed
        print(f"OpenAI API error: {e}")
        return {"intent": "unclear"}