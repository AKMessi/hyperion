import imaplib
import email
from email.header import decode_header
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional
import google.generativeai as genai
from src.hyperion.database.operations import get_prospect_by_email

def _decode_header(header):
    """
    Decodes email headers to a readable string.
    """

    decoded_parts = decode_header(header)
    header_str = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            header_str += part.decode(encoding or "utf-8")
        else:
            header_str += part
    return header_str

def _get_email_body(msg):
    """Extracts the plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode()
                except:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode()
        except:
            return ""

def ingest_and_filter_replies() -> List[Dict]:
    """
    Connects to the inbox, fetches unread emails, and filters for replies
    from known prospects in our database.
    """

    load_dotenv()

    user = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_APP_PASSWORD")

    if not user or not password: return []

    qualified_replies = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user, password)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            print("  - No unread messages found.")
            mail.logout()
            return []

        unread_email_ids = messages[0].split()
        latest_ids = unread_email_ids[-10:]
        print(f"  - Found {len(unread_email_ids)} total unread. Checking the 10 most recent...")

        for email_id in latest_ids:
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    from_header = _decode_header(msg["from"])
                    sender_email = email.utils.parseaddr(from_header)[1]
                    
                    prospect = get_prospect_by_email(sender_email)
                    if prospect:
                        print(f"  - ✅ Found reply from known prospect: {sender_email}")
                        subject = _decode_header(msg["subject"])
                        body = _get_email_body(msg)
                        qualified_replies.append({
                            "prospect_id": prospect["prospect_id"],
                            "from": sender_email,
                            "subject": subject,
                            "body": body.strip()
                        })
        
        mail.logout()

    except Exception as e:
        print(f"An error occurred: {e}")
    
    return qualified_replies

def classify_intent(email_body: str) -> Optional[str]:
    """
    Uses Gemini 2.5 Pro to classify the intent of an email reply.
    """

    print("\n --- Node: Classifying Intent ---")

    try:
        load_dotenv()
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("ERROR: GOOGLE_API_KEY not found.")
        genai.configure(api_key=google_api_key)
        model = genai.GenerativeModel("gemini-2.5-pro")

        prompt = (
            "You are an expert at classifying sales email replies. Analyze the email body and classify its intent into ONE of the following categories:\n"
            " - POSITIVE_INTEREST: The user is interested, asking for more info, or wants to schedule a meeting.\n"
            " - OBJECTION: The user is not interested right now, says the timing is bad, or they already have a solution.\n"
            " - QUESTION: The user is asking a specific question about the product or pricing.\n"
            " - NEGATIVE: The user is asking to be unsubscribed or is clearly angry.\n"
            " - OUT_OF_OFFICE: This is an automated out-of-office reply.\n"
            " - UNCATEGORIZED: The reply does not fit any of the above categories.\n\n"
            "--- EXAMPLES ---\n"
            "Email: 'This looks great, can we set up a time to chat next week?' -> Intent: POSITIVE_INTEREST\n"
            "Email: 'We're not focused on this at the moment.' -> Intent: OBJECTION\n"
            "Email: 'Unsubscribe' -> Intent: NEGATIVE\n"
            "Email: 'How does your pricing work?' -> Intent: QUESTION\n"
            "Email: 'I am out of the office until Friday.' -> Intent: OUT_OF_OFFICE\n"
            "--- END EXAMPLES ---\n\n"
            f"Now, classify the following email body. Respond with ONLY the category name and nothing else:\n\n"
            f"'{email_body}'"
        )

        response = model.generate_content(prompt)
        intent = response.text.strip()
        print(f" - Classified Intent: {intent}")
        return intent
    
    except Exception as e:
        print(f" - An error occurred during intent classification: {e}")
        return None