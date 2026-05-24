from __future__ import annotations

from openai import AsyncOpenAI

from src.config.settings import Settings
from src.database.repository import Repository


class MemoryStore:
    def __init__(self, settings: Settings, repository: Repository | None = None):
        self.settings = settings
        self.repository = repository or Repository()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def remember_conversation(self, conversation_id: str, text: str, metadata: dict) -> None:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is required for memory embeddings.")
        embedding = await self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=text,
        )
        self.repository.client.table("conversation_memories").insert(
            {
                "conversation_id": conversation_id,
                "content": text,
                "embedding": embedding.data[0].embedding,
                "metadata": metadata,
                "created_by": "system",
                "updated_by": "system",
            }
        ).execute()
