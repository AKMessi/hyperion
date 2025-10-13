from agents.research_agent import build_agent_graph, generate_email

if __name__ == "__main__":
    print("--- Initializing Hyperion Agent ---")
    
    # build the compiled agent graph
    app = build_agent_graph()

    # define the prospect to research
    mock_prospect = {
        "name": "Harry Dry",
        "title": "Founder", # Add title for the email generation step
        "organization": { "name": "Marketing Examples" }
    }
    
    # initial input
    inputs = {
        "prospect": mock_prospect,
        "max_retries": 1 
    }

    print("\n--- Invoking Agent for Research ---")
    # run the entire research graph from start to finish
    final_state = app.invoke(inputs)

    print("\n\n--- RESEARCH PHASE COMPLETE ---")
    
    hook = final_state.get('hook')

    if hook:
        print(f"Successfully generated hook: '{hook}'")
        
        # email generation
        final_email = generate_email(mock_prospect, hook)
        
        if final_email:
            print("\n✅ --- GENERATION COMPLETE ---")
            print("Final Email Output:")
            print("---------------------------------")
            print(final_email)
            print("---------------------------------")
        else:
            print("\n❌ Agent failed at Email Generation stage.")
    else:
        print("\n❌ Research agent failed to produce a hook. Halting process.")


    print("\n--- Hyperion Test Finished ---")