from src.hyperion.email_sender import send_email

if __name__ == "__main__":
    print("--- Starting Hyperion Test: Email Sender ---")
    
    # IMPORTANT: Change this to an email address you can check!
    recipient_email = "aaryankakad1@gmail.com"
    
    test_subject = "Hyperion Test Email"
    test_body = (
        "This is a test of the Hyperion Email Sender component.\n\n"
        "If you are reading this, the system is operational.\n\n"
        "Regards,\nHyperion-Architect"
    )

    send_email(recipient_email, test_subject, test_body)
    
    print("--- Test Finished ---")