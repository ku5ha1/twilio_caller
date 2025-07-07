from google import genai
from dotenv import load_dotenv
import os

class ScriptGenerator:
    def __init__(self):
        load_dotenv()
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API Key not found")
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def generate_script(self, topic="AI in Dubai Real Estate"):
        prompt = f"""
Generate a 100-word Instagram Reel script on the topic 'Usage of AI in Dubai Real Estate,' written exclusively for Veena, a middle-aged female real estate broker, to deliver directly to the audience. The script should be engaging, conversational, and tailored as if Veena is speaking to viewers in a relatable yet professional tone. Include relevant statistics or examples to highlight how AI has transformed key segments of the UAE real estate market (e.g., property search, valuations, virtual tours, or customer service). Avoid any extraneous text like scene directions, shot descriptions, or labels (e.g., '[Intro music]'). The output should ONLY contain the spoken script—nothing else.
"""

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text