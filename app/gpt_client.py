import os
from openai import OpenAI
from app.config import OPENAI_API_KEY

class GptClient:
    DEFAULT_PROMPT_TEMPLATE = "Generate a 300 word content about: {topic} - this is a script for an engaging video that can be read aloud clearly by a human. Make sure the response is not like a complete script for the video - it should just be the content that needs to be read out by the narrator. Make the content engaging, attention catching and informative"

    def __init__(self, api_key=OPENAI_API_KEY, model="gpt-4o-2024-05-13"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.prompt_template = self.DEFAULT_PROMPT_TEMPLATE

    async def generate_script(self, topic: str) -> str:
        prompt = self.prompt_template.format(topic=topic)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500  # Increased max_tokens to accommodate longer scripts
            )
            if response.choices and response.choices[0].message.content:
                # Remove newline characters and any leading/trailing whitespace
                cleaned_script = response.choices[0].message.content.strip().replace('\n', ' ')
                return cleaned_script
            else:
                return "Error: Could not generate script."
        except Exception as e:
            return f"Error generating script: {e}"

# Example usage (for testing)
async def test_gpt_client():
    gpt_client = GptClient()
    topic = "the benefits of drinking water"
    script = await gpt_client.generate_script(topic)
    print(f"Generated Script:\n{script}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_gpt_client())