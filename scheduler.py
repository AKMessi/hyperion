import time
from datetime import datetime, timezone

from src.hyperion.database.operations import (
    initialize_database, get_due_actions,
    update_sequence_after_send, get_prospect_by_id,
    update_prospect_status  # Import the status update function
)
from src.hyperion.email_sender import send_email
from src.hyperion.agents.research_agent import build_agent_graph, generate_email

def run_scheduler():
    """
    The final, production-ready scheduler. It uses the template-driven
    email generator and intelligently handles research failures.
    """
    print("--- Hyperion Scheduler [v4.0 FINAL] is starting up... ---")
    initialize_database()
    research_agent = build_agent_graph()
    
    while True:
        try:
            print(f"\n[{datetime.now(timezone.utc)}] Scheduler waking up...")
            due_actions = get_due_actions()
            
            if not due_actions:
                print("  - No actions due.")
            else:
                print(f"  - Found {len(due_actions)} due action(s). Processing...")
                
                for i, action in enumerate(due_actions):
                    print(f"\n--- Processing action {i+1} of {len(due_actions)} ---")
                    prospect_id = action['prospect_id']
                    prospect = get_prospect_by_id(prospect_id)
                    
                    if not prospect:
                        print(f"  - Skipping: Prospect data not found for id {prospect_id}")
                        update_prospect_status(prospect_id, 'failed') # Mark as failed
                        continue

                    print(f"    -> Processing Step {action['current_step']} for {prospect['name']}...")
                    
                    if action['current_step'] == 1:
                        print("    -> Running AI Research for Step 1...")
                        agent_input = {"prospect": prospect}
                        final_state = research_agent.invoke(agent_input)
                        hook = final_state.get('hook')

                        # This is our new quality gate
                        if hook and "No compelling hook found." not in hook:
                            print(f"    -> AI Research successful. Hook: '{hook}'")
                            email_content = generate_email(prospect, hook)
                            
                            if email_content:
                                try:
                                    subject = email_content.split('Subject: ')[1].split('\n')[0]
                                    body = email_content.split('\n\n', 1)[1]
                                    email_sent = send_email(prospect['email'], subject, body)
                                    
                                    if email_sent:
                                        update_sequence_after_send(action['prospect_sequence_id'], action['current_step'], 3)
                                        print(f"    -> Action complete. Email sent and prospect rescheduled.")
                                        if i < len(due_actions) - 1:
                                            print(f"    -> Pacing delay: Waiting 5 minutes...")
                                            time.sleep(300)
                                except Exception as e:
                                    print(f"    - Error parsing or sending email: {e}")
                                    update_prospect_status(prospect_id, 'failed')
                        else:
                            # If the hook is invalid, log it, mark as failed, and skip.
                            print(f"    -> AI could not find a compelling hook. Skipping prospect.")
                            update_prospect_status(prospect_id, 'failed')
                            continue
                    else:
                        # Follow-up logic (currently placeholder)
                        print("    -> Follow-up steps not yet implemented. Finishing sequence.")
                        update_prospect_status(prospect_id, 'finished')

            sleep_interval = 60
            print(f"\n--- Scheduler sleeping for {sleep_interval} seconds. ---")
            time.sleep(sleep_interval)

        except Exception as e:
            print(f"!! An error occurred in the scheduler loop: {e} !!")
            time.sleep(60)

if __name__ == "__main__":
    run_scheduler()
