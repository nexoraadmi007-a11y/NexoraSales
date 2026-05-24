from __future__ import annotations

from openai import AsyncOpenAI

from src.config.settings import Settings


class ConversationAssistant:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def analyze_chat(self, chat_text: str, business_context: str = "") -> str:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is required for conversation analysis.")
        prompt = f"""
You are the NEXORA SALESLEAD consultative sales copilot.
Analyze this customer chat and return exactly four sections:

🧠 Suggested Reply
🔥 Best Version
➡️ Next Step
📌 Operational Insight

Tone: human, strategic, intelligent, consultative. Avoid hype.
Business context: {business_context or "Unknown"}
Chat:
{chat_text}
"""
        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=prompt,
        )
        return response.output_text
