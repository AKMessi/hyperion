# Project Hyperion - Autonomous SDR

**Mission:** To autonomously execute personalized B2B sales outreach campaigns, leveraging AI for research, personalization, and execution. Project Hyperion serves as the foundational MVP for the AI agency "Get AI Simplified".

**Status:** MVP Complete. Ready for initial live campaign execution ("Operation: First Wave").

---

## Architecture Overview

Hyperion operates through a sequence of stages, orchestrated by a persistent scheduler and powered by AI agents:

1.  **Sourcing & Enrichment (Milestone 1 - Mocked):**
    * Prospect data is currently sourced manually (e.g., via CSV export from Apollo.io).
    * A utility script (`populate_db.py`) loads this data into the local SQLite database.
    * *Future Enhancement:* Integrate live Apollo.io API calls for automated sourcing and enrichment.

2.  **Research & Personalization (Milestone 2 - Complete):**
    * Employs the **"Ultimate Website-First"** architecture for generating personalized hooks.
    * **Agent Workflow:**
        * **(Node 1) `scrape_website`:** Uses Firecrawl to scrape raw markdown content from the prospect's company website (primary domain).
        * **(Node 2) `synthesize_hook_from_website`:** Uses Gemini 2.5 Pro and an advanced "v6" prompt template (`synthesize_hook_v6.md`) to filter the raw website content and generate a single, compelling, verifiable hook. Includes a "fail-safe" mechanism to return "No compelling hook found." if quality criteria aren't met.
    * *Future Enhancement:* Implement the "Dual-Pronged" architecture using Tavily for person-centric research alongside the website scrape for maximum relevance and fallback capability.

3.  **Email Generation (Milestone 2 - Complete):**
    * Uses Gemini 2.5 Pro and a sophisticated, externalized prompt template (`generate_email.md`) incorporating "Anti-Rules" to craft a professional, non-salesy, personalized email based on the generated hook.
    * Configuration (Agency Name, Value Prop) is loaded from the environment (`.env`).

4.  **Sequencing (Milestone 3 - Stage 5 Complete):**
    * **Database:** Uses SQLite (`hyperion.db`) to manage prospect data (`prospects` table) and sequence state (`prospect_sequences` table). The database auto-initializes if the file or tables are missing.
    * **Scheduler (`scheduler.py`):** A persistent background process that runs continuously.
        * Wakes up periodically (currently 60 seconds).
        * Queries the database for prospects due for an action (`get_due_actions`).
        * For Step 1 actions, invokes the full AI Research Agent.
        * Sends emails via Gmail SMTP (`email_sender.py`) using secure App Passwords.
        * Includes a 5-minute pacing delay between sends (`time.sleep(300)`).
        * Updates the prospect's state in the database upon successful send (`update_sequence_after_send`).
    * *Future Enhancement:* Implement logic to handle multi-step sequences based on templates stored in the database.

5.  **Triage (Milestone 3 - Stage 6 Complete):**
    * **Ingestor (`reply_parser.py`):** Uses IMAP to connect to the sender's inbox and fetch the 10 most recent unread emails.
    * **Filter:** Intelligently filters emails, processing only replies from known prospects present in the `prospects` database table.
    * **Classifier:** Uses Gemini 2.5 Pro and a few-shot prompt to classify the intent of qualified replies (`POSITIVE_INTEREST`, `OBJECTION`, `QUESTION`, `NEGATIVE`, `OUT_OF_OFFICE`, `UNCATEGORIZED`).
    * **Dispatcher:**
        * Updates the prospect's status to `replied` in the database (stopping further sequences).
        * If intent is `POSITIVE_INTEREST`, sends a notification email to the configured `SENDER_EMAIL`.
    * *Future Enhancement:* Build out dispatcher actions for other intents (e.g., adding to a CRM, alerting specific team members).

---

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd project-hyperion
    ```

2.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    # Activate the environment (macOS/Linux):
    source venv/bin/activate
    # Or (Windows):
    venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    * Copy `template.env` to a new file named `.env`.
    * Fill in the required API keys and configuration values in the `.env` file:
        * `GOOGLE_API_KEY`: For Gemini models.
        * `FIRECRAWL_API_KEY`: For website scraping.
        * `TAVILY_API_KEY`: *(Required for future "Dual-Pronged" agent)*.
        * `SERPER_API_KEY`: *(Used in earlier agent versions, potentially for future tools)*.
        * `SENDER_EMAIL`: Your Gmail/Google Workspace email address for sending/receiving.
        * `SENDER_APP_PASSWORD`: The 16-digit Google App Password for `SENDER_EMAIL`.
        * `AGENCY_NAME`: Your agency's name (e.g., "Get AI Simplified").
        * `AGENCY_VALUE_PROP`: Your agency's value proposition.
        * `APOLLO_API_KEY`: *(Currently unused due to mock data)*.

---

## Running the System (Operation: First Wave)

This procedure executes a live outreach campaign.

1.  **Prepare Prospect Data:**
    * Create a `prospects.csv` file in the project root directory.
    * Ensure it has the necessary columns (see `populate_db.py`): `First Name`, `Last Name`, `Email`, `Person Linkedin Url`, `Title`, `Company Name`, `Website`.

2.  **Populate the Database:**
    * Run the population script. This reads `prospects.csv` and adds the prospects to the `prospects` table in `hyperion.db`.
    ```bash
    python populate_db.py
    ```

3.  **Clean the Action Queue:**
    * Run the cleanup script to remove any old test actions.
    ```bash
    python clear_sequences.py
    ```

4.  **Start the Scheduler (Terminal 1):**
    * This process runs continuously. Keep this terminal open.
    ```bash
    python scheduler.py
    ```

5.  **Enroll Prospects & Launch (Terminal 2):**
    * Run the enrollment script. This finds all prospects in the database who aren't yet in a sequence and adds them to the scheduler's queue.
    ```bash
    python enroll_all.py
    ```

6.  **Monitor:**
    * Observe the output in **Terminal 1** to see the agent processing prospects.
    * Monitor the `SENDER_EMAIL` account's "Sent" folder.
    * Monitor the `SENDER_EMAIL` account's inbox for replies and triage notifications.

---

## Testing Reply Handling

The `main.py` script is configured for testing the Triage engine:

1.  Ensure the prospect who will "reply" exists in the database (use `populate_db.py` or manually add).
2.  Manually send a test email *from* the prospect's address *to* your `SENDER_EMAIL`.
3.  Ensure the test email is **unread** in the `SENDER_EMAIL` inbox.
4.  Run the test script:
    ```bash
    python main.py
    ```
    (Note: The current `main.py` may be configured differently based on the last test run. Update as needed.)

---

## Future Enhancements

* Implement live Apollo.io integration.
* Build out multi-step sequence logic.
* Implement full Action Dispatcher logic for all reply intents.
* Add structured logging and observability (database logging).
* Migrate database to PostgreSQL for production.
* Develop a web UI (Streamlit/Flask).
* Implement AI Guardrails (human approval step).
* Integrate the "Dual-Pronged" research architecture using Tavily.