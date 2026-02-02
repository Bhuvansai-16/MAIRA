import psycopg
from dotenv import load_dotenv
import os

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_PROJECT_REF = SUPABASE_URL.replace('https://', '').replace('.supabase.co', '')
SUPABASE_PASSWORD = os.getenv('MAIRA_PASSWORD', '')
DB_URI = f'postgresql://postgres:{SUPABASE_PASSWORD}@db.{SUPABASE_PROJECT_REF}.supabase.co:5432/postgres'

with psycopg.connect(DB_URI) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
        tables = [t[0] for t in cur.fetchall()]
        print(f'All tables: {tables}')
        
        # Show checkpoint_blobs structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'checkpoint_blobs'
            ORDER BY ordinal_position
        """)
        print('\ncheckpoint_blobs structure:')
        for col in cur.fetchall():
            print(f'  {col[0]}: {col[1]}')
