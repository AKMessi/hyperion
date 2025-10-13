from agents.research_agent import build_agent_graph

if __name__ == "__main__":
    print("--- Initializing Hyperion Agent ---")
    
    # build the compiled agent graph
    app = build_agent_graph()

    # define the prospect to research
    mock_prospect = {
        "name": "Changpeng Zhao",
        "organization": { "name": "Binance" }
    }
    
    # this is the initial input for our agent's state
    inputs = {
        "prospect": mock_prospect,
        "max_retries": 1
    }

    print("\n--- Invoking Agent ---")
    # the .invoke() method runs the entire graph from start to finish
    final_state = app.invoke(inputs)

    print("\n\n--- AGENT RUN COMPLETE ---")
    print(f"Prospect: {final_state['prospect']['name']}")
    print(f"Final Hook: {final_state['hook']}")