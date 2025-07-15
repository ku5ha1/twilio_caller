from openai import OpenAI
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def analyze_consent(transcript: str):
    prompt = f"""
    Is the following candidate response indicating consent to continue?

    Transcript: "{transcript}"

    Respond in JSON format:
    {{
      "proceed": true|false,
      "reason": "short explanation",
      "tone": "positive/neutral/negative"
    }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        # Parse the JSON output from the LLM
        result = json.loads(content)
        return result
    except Exception as e:
        # Log or handle the error as needed
        print(f"OpenAI API error: {e}")
        return {"proceed": False, "reason": "LLM error", "tone": "neutral"}