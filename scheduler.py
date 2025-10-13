import time
from datetime import datetime, timezone

from src.hyperion.database.operations import (
    initialize_database, get_due_actions,
    update_sequence_after_send, get_prospect_by_id
)
from src.hyperion.email_sender import send_email
from src.hyperion.agents.research_agent import build_agent_graph, generate_email

def run_scheduler():
    """
    The main scheduler loop. This version correctly uses the externalized
    prompt system by calling the final `generate_email` function.
    """
    print("--- Hyperion Scheduler [v3.0 FINAL] is starting up... ---")
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
                    
                    if not prospect or not prospect.get('email'):
                        print(f"  - Skipping: Prospect data not found for id {prospect_id}")
                        continue

                    print(f"    -> Processing Step {action['current_step']} for {prospect['name']}...")
                    email_content = None
                    
                    if action['current_step'] == 1:
                        print("    -> Running AI Research for Step 1...")
                        agent_input = {"prospect": prospect, "max_retries": 1}
                        final_state = research_agent.invoke(agent_input)
                        hook = final_state.get('hook')

                        if hook:
                            email_content = generate_email(prospect, hook)
                        else:
                            print("    - AI Research failed. Skipping for now.")
                            continue
                    else:
                        # Logic for follow-up emails
                        subject = "Following up"
                        body = f"Hi {prospect['name'].split(' ')[0]},\n\nJust following up on my previous email.\n\nBest,\nAaryan"
                        email_content = f"Subject: {subject}\n\n{body}"

                    if not email_content:
                        print(f"    - Failed to generate email content for {prospect['name']}. Skipping.")
                        continue

                    # Parse the subject and body from the generated content
                    try:
                        subject = email_content.split('Subject: ')[1].split('\n')[0]
                        body = email_content.split('\n\n', 1)[1]
                    except IndexError:
                        print(f"    - Error parsing generated email content. Using fallback.")
                        subject = "A thought"
                        body = email_content

                    email_sent = send_email(prospect['email'], subject, body)
                    
                    if email_sent:
                        wait_days = 3
                        update_sequence_after_send(
                            action['prospect_sequence_id'],
                            action['current_step'],
                            wait_days
                        )
                        print(f"    -> Action complete. Email sent and prospect rescheduled.")
                        
                        if i < len(due_actions) - 1:
                            print(f"    -> Pacing delay: Waiting 5 minutes before next email...")
                            time.sleep(300)
                    else:
                        print(f"    -> Email send failed. Will retry on next scheduler run.")

            sleep_interval = 60
            print(f"\n--- Scheduler sleeping for {sleep_interval} seconds. ---")
            time.sleep(sleep_interval)

        except Exception as e:
            print(f"!! An error occurred in the scheduler loop: {e} !!")
            time.sleep(60)

if __name__ == "__main__":
    run_scheduler()