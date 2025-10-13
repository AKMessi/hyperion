from src.hyperion.database.operations import add_prospect, enroll_prospect_in_sequence
from src.hyperion.database.operations import initialize_database

if __name__ == "__main__":
    initialize_database()

    real_world_prospect = {
        'id': 'prospect_aaryan_01',
        'name': 'Tim Cook',
        'email': 'aaryankakad1@gmail.com',
        'title': 'CEO',
        'organization': {
            'name': 'Apple',
            'primary_domain': 'apple.com'
        }
    }

    print(f"--- Enrolling a real-world test prospect: {real_world_prospect['name']} ---")
    add_prospect(real_world_prospect)
    enroll_prospect_in_sequence(real_world_prospect['id'], 'seq_standard_01')

    print("--- Enrollment complete. The scheduler now has a high-quality record to process. ---")