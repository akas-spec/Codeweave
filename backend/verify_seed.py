"""Verify seed user and health endpoint."""
import asyncio
import asyncpg
import httpx

async def main():
    # 1. Check seed user in DB
    print("=== Database Check ===")
    conn = await asyncpg.connect("postgresql://codeweave:codeweave@localhost:5434/codeweave")
    
    user = await conn.fetchrow("SELECT id, username, email, github_id FROM users WHERE id = 1")
    if user:
        print(f"  Seed user EXISTS: id={user['id']}, username={user['username']}, email={user['email']}, github_id={user['github_id']}")
    else:
        print("  ERROR: Seed user id=1 NOT FOUND")
    
    count = await conn.fetchval("SELECT count(*) FROM users")
    print(f"  Total users: {count}")
    
    tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
    print(f"  Tables: {[t['tablename'] for t in tables]}")
    
    await conn.close()
    
    # 2. Check health endpoint
    print("\n=== Health Endpoint ===")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8000/health", timeout=5.0)
            print(f"  Status: {resp.status_code}")
            print(f"  Body: {resp.json()}")
    except Exception as e:
        print(f"  Health check failed (backend may not be running): {e}")

asyncio.run(main())
