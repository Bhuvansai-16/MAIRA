import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
import os
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_PROJECT_REF = SUPABASE_URL.replace('https://', '').replace('.supabase.co', '')
SUPABASE_PASSWORD = os.getenv('MAIRA_PASSWORD', '')
DB_URI = f'postgresql://postgres:{SUPABASE_PASSWORD}@db.{SUPABASE_PROJECT_REF}.supabase.co:5432/postgres'

print('Connecting to PostgreSQL...')
with psycopg.connect(DB_URI, autocommit=True) as conn:
    # Drop existing LangGraph tables if they exist (to recreate with correct schema)
    with conn.cursor() as cur:
        print('Dropping old LangGraph checkpoint tables...')
        cur.execute('DROP TABLE IF EXISTS checkpoint_writes CASCADE;')
        cur.execute('DROP TABLE IF EXISTS checkpoints CASCADE;')
        print('Creating new LangGraph checkpoint tables...')
    
    # Run LangGraph setup
    PostgresSaver(conn).setup()
    print('✅ LangGraph schema created successfully!')
    
    # Verify tables and show their structure
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'checkpoint%'
        """)
        tables = cur.fetchall()
        print(f'\nLangGraph tables created: {[t[0] for t in tables]}')
        
        # Show checkpoints table structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'checkpoints'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        print('\nCheckpoints table structure:')
        for col in columns:
            print(f'  - {col[0]}: {col[1]}')
