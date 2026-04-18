import sqlite3
import os
import json
import logging
import inspect
from dotenv import load_dotenv

# Setup paths (one level up from scripts dir to Axis dir)
script_dir = os.path.dirname(os.path.abspath(__file__))
axis_dir = os.path.dirname(script_dir)
import sys
sys.path.append(axis_dir)

from jarvis_ai.db.supabase_client import get_supabase

# Loads .env from the project root
load_dotenv(os.path.join(axis_dir, '.env'))

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def migrate_table(sqlite_cursor, table_name, supabase_table=None):
    if supabase_table is None:
        supabase_table = table_name

    logger.info(f"Starting migration for {table_name} -> {supabase_table}...")
    
    # Check if table exists in SQLite
    sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not sqlite_cursor.fetchone():
        logger.warning(f"Table {table_name} does not exist in SQLite. Skipping.")
        return

    # Fetch rows
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        logger.info(f"No records found in {table_name}.")
        return
        
    logger.info(f"Found {len(rows)} records in {table_name}.")

    col_names = [description[0] for description in sqlite_cursor.description]
    
    supabase = get_supabase()
    
    success_count = 0
    error_count = 0

    # We do them row by row or small batches. Small batches is safer for type coercions
    for row in rows:
        row_dict = dict(zip(col_names, row))
        try:
            # Upsert by ID if it has an id column
            if 'id' in row_dict:
                supabase.table(supabase_table).upsert(row_dict).execute()
            else:
                supabase.table(supabase_table).insert(row_dict).execute()
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to migrate record {row_dict}: {e}")
            error_count += 1

    logger.info(f"Migrated {success_count} records to {supabase_table}. Errors: {error_count}")

def run_migration():
    supabase = get_supabase()
    try:
        # Check supabase works
        supabase.table("goals").select("id").limit(1).execute()
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        return

    # Connect to local SQLite jarvis_memory.db
    db_path = os.path.join(axis_dir, "jarvis_memory.db")
    if not os.path.exists(db_path):
        logger.error(f"SQLite database not found at {db_path}")
        return

    logger.info(f"Connecting to full memory DB: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables_to_migrate = [
        "system_settings",
        "goal_history",
        "llm_advisory_log",
        "conversations",
        "messages",
        "summaries",
        "pending_actions",
        "devices",
        "pairing_codes",
        "activity_log",
        "goals",
        "goal_plans",
        "goal_plan_steps",
        "goal_events",
        "permission_requests",
        "long_term_memory"
    ]

    for t in tables_to_migrate:
        migrate_table(cursor, t)

    conn.close()
    
    # Try reminders too
    reminders_db = os.path.join(axis_dir, "data", "reminders.db")
    if os.path.exists(reminders_db):
        logger.info(f"Found reminders DB: {reminders_db}")
        r_conn = sqlite3.connect(reminders_db)
        r_cursor = r_conn.cursor()
        migrate_table(r_cursor, "reminders")
        r_conn.close()

    logger.info("Migration completed.")

if __name__ == "__main__":
    run_migration()
