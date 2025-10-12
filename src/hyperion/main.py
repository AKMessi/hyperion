from clients.apollo_client import ApolloClient

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
    
    except ValueError as e:
        print(e)
    print("Hyperion Test Finished.")