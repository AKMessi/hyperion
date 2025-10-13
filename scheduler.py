import time
from datetime import datetime, timezone

from src.hyperion.database.operations import get_due_actions, update_sequence_after_send
from src.hyperion.database.operations import initialize_database

def run_scheduler():
    """
    The main scheduler loop that runs continuously to process due actions.
    """

    print("--- Hyperion Scheduler is starting up... ---")

    initialize_database()

    while True:
        try:
            print(f"\n [{datetime.now(timezone.utc)}] Scheduler waking up to check for due actions...")

            due_actions = get_due_actions()

            if not due_actions:
                print("- No actions due at this time.")

            else:
                print(f" - Found {len(due_actions)} due action(s). Processing...")
                for action in due_actions:
                    print(f" -> Processing action for prospect_id: {action['prospect_id']}, Step: {action['current_step']}")

                    print(f" -> (SIMULATING EMAIL SEND)")

                    wait_days_for_next_step = 3

                    update_sequence_after_send(
                        prospect_sequence_id=action['prospect_sequence_id'],
                        current_step=action['current_step'],
                        wait_days_for_next_step=wait_days_for_next_step
                    )

                    print(f" -> Action complete. Prospect rescheduled for {wait_days_for_next_step} days from now.")

            sleep_interval = 60
            print(f"--- Scheduler going to sleep for {sleep_interval} seconds. ---")
            time.sleep(sleep_interval)

        except Exception as e:
            print(f"An error occurred in the scheduler loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_scheduler()