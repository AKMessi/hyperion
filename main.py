from src.hyperion.reply_parser import ingest_and_filter_replies, classify_intent

if __name__ == "__main__":
    print("--- Starting Hyperion Test: Full Triage Chain ---")
    
    # We don't need to add the prospect to the DB for this test,
    # as they should still be in there from the last run.
    
    print("\n-> Running the reply ingestor and filter...")
    replies = ingest_and_filter_replies()

    if replies:
        print(f"\n✅ Filtered and found {len(replies)} qualified reply/replies.")
        
        # Process the first qualified reply
        reply = replies[0]
        print(f"  - Processing reply from: {reply['from']}")
        
        # --- THE FINAL AI STEP ---
        # Classify the intent of the email body
        intent = classify_intent(reply['body'])
        
        if intent:
            print(f"\n✅ --- TRIAGE COMPLETE ---")
            print(f"  - Prospect ID: {reply['prospect_id']}")
            print(f"  - Subject: {reply['subject']}")
            print(f"  - Intent: {intent}")
            print("-------------------------")
        else:
            print("\n❌ Failed to classify the email's intent.")
    else:
        print("\n--- Test finished. No replies from known prospects were found. ---")