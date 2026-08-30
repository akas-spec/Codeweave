import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User

async def test():
    async with AsyncSessionLocal() as session:
        # String parameter to integer column
        user_id = "2"
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        print(f"User found: {user.username if user else None}")

asyncio.run(test())
