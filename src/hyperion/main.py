from clients.apollo_client import ApolloClient
from agents.research_agent import execute_web_search, scrape_and_summarize_content, generate_search_queries

if __name__ == "__main__":
    print("--- Starting Hyperion Test: Stage 1 Sourcing ---")
    try:
        client = ApolloClient()

        search_titles = ["VP of Engineering", "Head of Enginering"]
        search_locations = ["California", "USA"]
        search_employees = ["51,200"]

        prospects = client.search_people_mock(
            titles=search_titles,
            locations=search_locations,
            company_employee_counts=search_employees
        )

        if prospects is not None:
            print(f"Successfully found {len(prospects)} prospects.")

            if prospects:
                first_prospect = prospects[0]
                print("\n Sample Prospect Data: ")
                print(f"Name: {first_prospect.get('name')}")
                print(f"Title: {first_prospect.get('title')}")
                print(f"Company: {first_prospect.get('organization', {}).get('name')}")
                print(f"Email status: {first_prospect.get('email_status')}")

        else:
            print("Failed to retrieve prospects.")
        
        
        print("--- Starting Hyperion Test: Full Research Chain ---")
        test_query = "IBM WatsonX new features 2025"

        search_results = execute_web_search(test_query)

        if search_results:
            first_result_link = search_results[0].get('link')

            if first_result_link:
                summary = scrape_and_summarize_content(first_result_link)

                if summary:
                    print(f"\n Research Complete.")
                    print(f"Source URL: {first_result_link}")
                    print(f"Generated Summary: \n {summary}")

                else:
                    print("Failed to generate a summary for the article.")

            else:
                print(f"No link found in the first search result.")

        else:
            print("Failed to retrieve search results.")

        print("--- Starting Hyperion Test: Research Agent - Query Generation ---")

        mock_prospect = {
            "id": "mock_contact_67890",
            "name": "Satya Nadella",
            "organization": {"name": "Microsoft"}
        }

        queries = generate_search_queries(mock_prospect)

        if queries:
            print(f" --- Query Generation Complete ---")
            print("Generated Queries: ")
            for q in queries:
                print(f" - {q}")
        
        else:
            print("Failed to generate search queries.")

    except ValueError as e:
        print(e)
    print("Hyperion Test Finished.")