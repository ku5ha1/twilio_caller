import os
from openai import OpenAI
from app.config import OPENAI_API_KEY

class GptClient:
    DEFAULT_PROMPT_TEMPLATE = "Generate a comprehensive video script about: {topic} - this is a script for a reel"

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
                max_tokens=200  # Adjust as needed
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
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