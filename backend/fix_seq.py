import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def fix_seq():
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));"))
        await session.commit()
        print("Sequence fixed!")

if __name__ == "__main__":
    asyncio.run(fix_seq())
