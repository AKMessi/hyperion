import sqlite3
from src.hyperion.config import DATABASE_FILE
from src.hyperion.database.operations import initialize_database, enroll_prospect_in_sequence

def enroll_all_prospects(sequence_id='seq_standard_01'):
    """Finds all prospects in the DB and enrolls them in a sequence."""
    initialize_database()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.prospect_id FROM prospects p
        LEFT JOIN prospect_sequences ps ON p.prospect_id = ps.prospect_id
        WHERE ps.prospect_id IS NULL
    """)
    prospects_to_enroll = cursor.fetchall()
    conn.close()
    
    if not prospects_to_enroll:
        print("No new prospects to enroll.")
        return

    print(f"Found {len(prospects_to_enroll)} new prospects. Enrolling them in {sequence_id}...")
    
    for prospect_tuple in prospects_to_enroll:
        prospect_id = prospect_tuple[0]
        enroll_prospect_in_sequence(prospect_id, sequence_id)
        
    print("Enrollment complete.")

if __name__ == '__main__':
    enroll_all_prospects()