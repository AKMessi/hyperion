import sqlite3
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime, timezone, timedelta
from src.hyperion.config import DATABASE_FILE

def initialize_database():
    """
    Creates and initializes all database tables if they don't exist.
    """

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prospects (
            prospect_id TEXT PRIMARY KEY, full_name TEXT, email TEXT UNIQUE,
            linkedin_url TEXT, title TEXT, company_name TEXT, company_domain TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prospect_sequences (
            prospect_sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id TEXT NOT NULL, sequence_id TEXT NOT NULL,
            status TEXT NOT NULL, current_step INTEGER NOT NULL,
            next_action_timestamp TIMESTAMP,
            FOREIGN KEY (prospect_id) REFERENCES prospects (prospect_id),
            UNIQUE (prospect_id, sequence_id)
        )
    ''')

    print("-> `initialize_database`: Tables created or verified.")

    conn.commit()
    conn.close()

def add_prospect(prospect: Dict):
    """
    Adds a new prospect to the database, ignoring if email already exists.
    """

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    sql = ''' INSERT OR IGNORE INTO prospects (prospect_id, full_name, email, linkedin_url, title, company_name, company_domain)
              VALUES (?, ?, ?, ?, ?, ?, ?) '''
    
    cursor.execute(sql, (
        prospect.get('id', ''), prospect.get('name', ''), prospect.get('email', ''),
        prospect.get('linkedin_url', ''), prospect.get('title', ''),
        prospect.get('organization', {}).get('name', ''),
        prospect.get('organization', {}).get('primary_domain', '')
    ))

    conn.commit()
    conn.close()

def get_prospect_by_email(email: str) -> Optional[Dict]:
    """
    Reads a prospect's data from the database using their email.
    """

    conn = sqlite3.connect(DATABASE_FILE)

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql_command = "SELECT * FROM prospects WHERE email = ?"

    cursor.execute(sql_command, (email,))

    prospect_row = cursor.fetchone()

    conn.close()

    if prospect_row:
        return dict(prospect_row)
    return None

def enroll_prospect_in_sequence(prospect_id: str, sequence_id: str):
    """
    Enrolls a prospect into a sequence, setting them up for Step 1.
    Sets the next action to the current time to be sent immediately.
    """

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    sql_command = '''
        INSERT OR IGNORE INTO prospect_sequences (
            prospect_id, sequence_id, status, current_step, next_action_timestamp
        ) VALUES (?, ?, ?, ?, ?)
    '''

    now_utc = datetime.now(timezone.utc)

    initial_status = 'active'
    initial_step = 1

    cursor.execute(sql_command, (
        prospect_id,
        sequence_id,
        initial_status,
        initial_step,
        now_utc
    ))

    conn.commit()
    conn.close()

    print(f" - Enrolled propsect {prospect_id} in sequence {sequence_id}.")

def get_due_actions() -> list:
    """
    Reads the database to find all prospects who are due for their next sequence step.
    """

    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    now_utc = datetime.now(timezone.utc)

    sql_command = """
        SELECT * FROM prospect_sequences
        WHERE status = 'active' AND next_action_timestamp <= ?
    """

    cursor.execute(sql_command, (now_utc,))

    due_actions = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return due_actions

def update_sequence_after_send(prospect_sequence_id: int, current_step: int, wait_days_for_next_step: int):
    """
    Updates a prospect's sequence state after an email is sent.
    Increments the step and schedules the next action.
    """

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    next_step = current_step + 1

    next_action_time = datetime.now(timezone.utc) + timedelta(days=wait_days_for_next_step)

    sql_command = """
        UPDATE prospect_sequences
        SET current_step = ?, next_action_timestamp = ?
        WHERE prospect_sequence_id = ?
    """

    cursor.execute(sql_command, (
        next_step,
        next_action_time,
        prospect_sequence_id
    ))

    conn.commit()
    conn.close()
    print(f"- Updated prospect_sequence_id {prospect_sequence_id} to Step {next_step}. Next action in {wait_days_for_next_step} days.")

def get_sequence_state_by_id(prospect_sequence_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prospect_sequences WHERE prospect_sequence_id = ?", (prospect_sequence_id,))
    record = cursor.fetchone()
    conn.close()
    return dict(record) if record else None

def get_prospect_by_id(prospect_id: str) -> Optional[Dict]:
    """
    Reads a prospect's data from the database using their unique prospect_id
    and reconstructs the nested dictionary format the agent expects.
    """
    
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()

    sql_command = "SELECT * FROM prospects WHERE prospect_id = ?"
    
    cursor.execute(sql_command, (prospect_id,))
    
    prospect_row = cursor.fetchone()
    
    conn.close()
    
    if prospect_row:
        return {
            "id": prospect_row["prospect_id"],
            "name": prospect_row["full_name"],
            "email": prospect_row["email"],
            "linkedin_url": prospect_row["linkedin_url"],
            "title": prospect_row["title"],
            "organization": {
                "name": prospect_row["company_name"],
                "primary_domain": prospect_row["company_domain"]
            }
        }
    return None

def clear_all_sequence_actions():
    """
    Deletes all records from the prospect_sequences table.
    This is useful for resetting the scheduler's queue during testing.
    """

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    sql_command = "DELETE FROM prospect_sequences"

    cursor.execute(sql_command)
    
    rows_deleted = cursor.rowcount

    conn.commit()
    conn.close()
    
    print(f"-> Cleared the 'prospect_sequences' table. {rows_deleted} action(s) removed.")