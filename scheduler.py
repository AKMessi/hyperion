import time
from datetime import datetime, timezone

from src.hyperion.database.operations import (
    initialize_database, get_due_actions,
    update_sequence_after_send, get_prospect_by_id # <-- Use the correct import
)
from src.hyperion.email_sender import send_email
from src.hyperion.agents.research_agent import build_agent_graph

def run_scheduler():
    print("--- Hyperion Scheduler [v2.1 CORRECTED] is starting up... ---")
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
                for action in due_actions:
                    prospect_id = action['prospect_id']
                    
                    prospect = get_prospect_by_id(prospect_id)
                    
                    if not prospect or not prospect.get('email'):
                        print(f"  - Skipping: Prospect data not found for id {prospect_id}")
                        continue

                    # ... (the rest of the loop is the same) ...
                    print(f"    -> Processing Step {action['current_step']} for {prospect['name']}...")
                    subject, body = "", ""
                    
                    if action['current_step'] == 1:
                        print("    -> Running AI Research for Step 1...")
                        agent_input = {"prospect": prospect, "max_retries": 1}
                        final_state = research_agent.invoke(agent_input)
                        hook = final_state.get('hook')

                        if hook:
                            subject = f"A thought on {prospect['organization']['name']}"
                            body = f"Hi {prospect['name'].split(' ')[0]},\n\n{hook}\n\nThis insight came from an autonomous agent we built at Hyperion. Curious how it works?\n\nBest,\nAaryan"
                        else:
                            print("    - AI Research failed. Skipping for now.")
                            continue
                    else:
                        subject = "Following up"
                        body = f"Hi {prospect['name'].split(' ')[0]},\n\nJust following up on my previous email.\n\nBest,\nAaryan"

                    email_sent = send_email(prospect['email'], subject, body)
                    
                    if email_sent:
                        wait_days = 3
                        update_sequence_after_send(
                            action['prospect_sequence_id'],
                            action['current_step'],
                            wait_days
                        )
                        print(f"    -> Action complete. Email sent and prospect rescheduled.")
                    else:
                        print(f"    -> Email send failed. Will retry on next scheduler run.")

            sleep_interval = 60
            print(f"--- Scheduler sleeping for {sleep_interval} seconds. ---")
            time.sleep(sleep_interval)

        except Exception as e:
            print(f"!! An error occurred in the scheduler loop: {e} !!")
            time.sleep(60)

if __name__ == "__main__":
    run_scheduler()