from src.hyperion.database.operations import initialize_database, add_prospect, get_prospect_by_id
from src.hyperion.agents.research_agent import build_agent_graph, generate_email
from src.hyperion.config import DATABASE_FILE
import os

if __name__ == "__main__":
    print("--- Starting Hyperion Test: Upgraded 'Website-First' Agent ---")
    
    # Step 1: Initialize the database to ensure it's ready.
    initialize_database()
    print("-> Database initialized.")

    # Step 2: Define a high-quality test prospect.
    # The agent will use the 'primary_domain' to find the website.
    mock_prospect = {
        'id': 'prospect_final_test_01',
        'name': 'Amirani Azaladze',
        'email': 'a.azaladze@b2bhub.ge',
        'title': 'Co-Founder',
        'organization': {
            'name': 'B2B Hub',
            'primary_domain': 'b2bhub.ge' # The agent will scrape this URL
        }
    }
    
    # Add the prospect to the DB (this also serves as a quick DB test)
    add_prospect(mock_prospect)
    print(f"-> Ensured prospect '{mock_prospect['name']}' is in the database.")

    # Step 3: Build and invoke the autonomous research agent.
    print("\n--- Invoking Agent for Research ---")
    research_agent = build_agent_graph()
    
    # The agent's input is a dictionary matching the structure of our AgentState
    agent_input = { "prospect": mock_prospect }
    
    # Run the agent from start to finish
    final_state = research_agent.invoke(agent_input)

    print("\n\n--- RESEARCH PHASE COMPLETE ---")
    
    # Step 4: Extract the results from the agent's final state.
    hook = final_state.get('hook')
    source_url = final_state.get('source_url')

    if hook and source_url:
        print(f"  - Source URL: {source_url}")
        print(f"  - Generated Hook: '{hook}'")
        
        # Step 5: If research was successful, generate the final email.
        final_email = generate_email(mock_prospect, hook)
        
        if final_email:
            print("\n✅ --- GENERATION COMPLETE ---")
            print("Final Email Output:")
            print("---------------------------------")
            print(final_email)
            print("---------------------------------")
        else:
            print("\n❌ Agent failed at the Email Generation stage.")
    else:
        print("\n❌ Research agent failed to produce a valid hook or source URL.")

    print("\n--- Hyperion Test Finished ---")
