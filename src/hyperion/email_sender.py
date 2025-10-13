import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Sends an email using Gmail's SMTP server.

    Returns:
        True if the email was sent successfully, False otherwise.
    """

    load_dotenv()

    sender_email = os.getenv("SENDER_EMAIL")
    app_password = os.getenv("SENDER_APP_PASSWORD")

    if not sender_email or not app_password:
        print("Error: SENDER_EMAIL or SENDER_APP_PASSWORD not found in the environment variables.")
        return False
    
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = to_email

    part1 = MIMEText(body, "plain")
    message.attach(part1)

    context = ssl.create_default_context()

    try:
        print(f"Connecting to Gmail SMTP server to send email to {to_email}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, message.as_string())
            return True
    
    except Exception as e:
        print(f"Error sending email: {e}")
        return False