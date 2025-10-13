# main.py - Final Guided Triage Test

from src.hyperion.database.operations import initialize_database, add_prospect, get_prospect_by_id, clear_all_sequence_actions
from src.hyperion.reply_parser import ingest_and_filter_replies, classify_intent, dispatch_action
import os

def run_final_test():
    """A guided, interactive test for the full triage workflow."""
    
    # --- SETUP ---
    print("--- Starting Final Guided Test for Hyperion Triage Engine ---")
    initialize_database()
    clear_all_sequence_actions() # Start with a clean queue

    prospect_email_to_reply_from = 'kakadaaryan10@gmail.com'
    app_email_to_receive_reply = os.getenv("SENDER_EMAIL")

    test_prospect = {
        'id': 'prospect_final_test_01',
        'name': 'Final Test',
        'email': prospect_email_to_reply_from,
        'title': 'Lead Prospect',
        'organization': {'name': 'Final Test Inc.'}
    }
    add_prospect(test_prospect)
    print(f"\nStep 1: Prospect '{prospect_email_to_reply_from}' has been added/verified in the database.")

    # --- MANUAL ACTION REQUIRED ---
    print("\n" + "="*60)
    print(">>> ACTION REQUIRED <<<")
    print(f"Please manually send a test email NOW with the following details:")
    print(f"  - FROM: {prospect_email_to_reply_from}")
    print(f"  - TO:   {app_email_to_receive_reply}")
    print(f"  - SUBJECT: Final Test Run")
    print(f"  - BODY:    This looks very interesting, please send more details.")
    print("="*60)
    
    input("\n>>> Once the email is sent and appears as UNREAD in the inbox, press Enter to continue...")

    # --- TRIAGE EXECUTION ---
    print("\nStep 2: Resuming script. Ingesting and filtering replies...")
    replies = ingest_and_filter_replies()

    if replies:
        reply = replies[0]
        prospect = get_prospect_by_id(reply['prospect_id'])
        
        if prospect:
            intent = classify_intent(reply['body'])
            
            if intent:
                dispatch_action(prospect, intent)
                print(f"\n✅ --- FULL TRIAGE COMPLETE ---")
                print(f"  - Prospect: {prospect['full_name']}")
                print(f"  - Intent: {intent}")
                print(f"  - Action: Dispatched (Notification sent to {app_email_to_receive_reply})")
                print("---------------------------------")
    else:
        print("\n❌ --- TEST FAILED ---")
        print("No qualified reply was found. Please check:")
        print("  1. The reply was sent FROM the correct address.")
        print("  2. The reply was sent TO the correct address.")
        print("  3. The reply was UNREAD in the inbox when you pressed Enter.")

if __name__ == "__main__":
    run_final_test()