import uuid
from src.hyperion.database.operations import add_prospect, enroll_prospect_in_sequence
from src.hyperion.database.operations import initialize_database

if __name__ == "__main__":
    initialize_database()

    unique_id = str(uuid.uuid4())[:8]
    mock_prospect = {
        'id': f'prospect_{unique_id}',
        'name': f'Test Prospect {unique_id}',
        'email': f'test_{unique_id}@example.com'
    }

    print(f"--- Enrolling a new test prospect: {mock_prospect['name']} ---")
    add_prospect(mock_prospect)
    enroll_prospect_in_sequence(mock_prospect['id'], 'seq_standard_01')

    print("--- Enrollment complete. The scheduler should pick this up on its next run. ---")