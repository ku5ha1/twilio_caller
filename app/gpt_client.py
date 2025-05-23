import os
from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY

class GptClient:
    DEFAULT_PROMPT_TEMPLATE = (
        "Generate a 300-word content about: {topic}. "
        "This is a script for an engaging video that can be read aloud clearly by a human. "
        "Do not format it like a complete video script — just provide the content to be read out by the narrator. "
        "Make it engaging, attention-catching, and informative."
    )

    def __init__(self, api_key=OPENAI_API_KEY, model="gpt-3.5-turbo"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.prompt_template = self.DEFAULT_PROMPT_TEMPLATE

    async def generate_script(self, topic: str) -> str:
        prompt = self.prompt_template.format(topic=topic)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip().replace('\n', ' ')
            else:
                return "Error: Could not generate script."
        except Exception as e:
            return f"Error generating script: {e}"