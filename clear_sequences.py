from src.hyperion.database.operations import initialize_database, clear_all_sequence_actions

if __name__ == "__main__":
    print("--- Hyperion Database Reset Utility ---")
    
    initialize_database()
    
    clear_all_sequence_actions()
    
    print("--- Reset complete. ---")