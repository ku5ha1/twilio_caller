from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from app.config import ELEVENLABS_API_KEY

class ElevenLabsClient:
    def __init__(self, api_key=ELEVENLABS_API_KEY, voice="21m00Tcm4TlvDq8ikWAM", model="eleven_multilingual_v2"):
        self.client = ElevenLabs(api_key=api_key)
        self.voice = voice
        self.model = model

    async def generate_audio(self, text: str) -> bytes:
        try:
            # Use the new text_to_speech.convert method
            audio_generator = self.client.text_to_speech.convert(
                voice_id=self.voice,
                model_id=self.model,
                text=text,
                voice_settings=VoiceSettings(stability=0.7, similarity_boost=0.8)
            )

            # Concatenate all chunks into a single bytes object
            audio_data = b"".join(chunk for chunk in audio_generator)
            return audio_data

        except Exception as e:
            raise Exception(f"Error generating audio with ElevenLabs: {e}")