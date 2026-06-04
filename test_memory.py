import asyncio
import os
from app.services.user_memory import extract_and_store_user_memories

async def test():
    stored = await extract_and_store_user_memories(
        user_id="test@example.com",
        session_id="test_session",
        user_prompt="I am a software engineer working primarily with React and Python.",
        assistant_response="That's great! React and Python are a powerful combination for full-stack development.",
        chat_history=[]
    )
    print("Stored items:", stored)

if __name__ == "__main__":
    asyncio.run(test())
