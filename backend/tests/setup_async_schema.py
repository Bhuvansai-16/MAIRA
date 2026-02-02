import asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_PROJECT_REF = SUPABASE_URL.replace('https://', '').replace('.supabase.co', '')
SUPABASE_PASSWORD = os.getenv('MAIRA_PASSWORD', '')
DB_URI = f'postgresql://postgres:{SUPABASE_PASSWORD}@db.{SUPABASE_PROJECT_REF}.supabase.co:5432/postgres'

async def main():
    print('Setting up AsyncPostgresSaver schema...')
    
    # Create connection pool
    pool = AsyncConnectionPool(conninfo=DB_URI, min_size=1, max_size=5, open=False)
    await pool.open()
    
    # Create saver and run setup
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    
    print('✅ AsyncPostgresSaver schema created successfully!')
    
    # List tables
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'checkpoint%'
                ORDER BY table_name
            """)
            tables = await cur.fetchall()
            print(f'Checkpoint tables: {[t[0] for t in tables]}')
    
    await pool.close()
    print('Done!')

if __name__ == '__main__':
    asyncio.run(main())
