from agents.research_agent import (
    generate_search_queries,
    execute_web_search,
    scrape_and_summarize_content,
    synthesize_hook
)

if __name__ == "__main__":
    print("--- Starting Hyperion Test: Full Agent Logic Chain ---")

    mock_prospect = {
        "name": "Arvind Nanda",
        "organization": {"name": "Interarch Building Products"}
    }

    # node 1: generate search queries
    queries = generate_search_queries(mock_prospect)
    if not queries:
        print("Failed to generate queries.")

    else:
        print(f"\b Generated Queries: {queries}")
        top_query = queries[0]

        # node 2: websearch
        search_results = execute_web_search(top_query)
        if not search_results:
            print("Failed to execute web search.")

        else:
            first_link = search_results[0].get('link')

            summary = scrape_and_summarize_content(first_link)
            if not summary:
                print("Failed to scrape and summarize the content.")

            else:
                print(f"\n Generated Summary: \n {summary} \n")

                hook = synthesize_hook(summary, mock_prospect['name'])
                if not hook:
                    print("Failed to generate hook.")

                else:
                    print("--- AGENT RUN COMPLETE ---")
                    print(f"Prospect: {mock_prospect['name']}")
                    print(f"Source URL: {first_link}")
                    print(f"Final Hook: {hook}")

    print("--- Hyperion Test Finished ---")