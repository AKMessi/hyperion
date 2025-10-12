import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Optional

class ApolloClient:
    """
    A client for interacting with the Apollo.io API.
    """

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("APOLLO_API_KEY")
        if not self.api_key:
            raise ValueError("ERROR: APOLLO_API_KEY not found in environment variables.")
        
    base_url = "https://api.apollo.io/v1/"

    def search_people(
        self,
        titles: List[str],
        locations: List[str],
        company_employee_counts: List[str]
    ) -> Optional[List[Dict]]:
        
        """
        Stage 1 & 2: Sources and retrieves detailed prospect data.
        This function now uses the 'mixed_people/search' endpoint.
        """

        url = self.base_url + "mixed_people/search" 

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key
        }

        payload = {
            "q_organization_domains": "",
            "person_titles": titles,
            "person_locations": locations,
            "organization_num_employees_ranges": company_employee_counts
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return data.get('contacts', [])

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err} - Status Code: {response.status_code} - Response: {response.text}")
        except requests.exceptions.RequestException as err:
            print(f"An error occurred: {err}")
        
        return None
    
    def search_people_mock(
        self,
        titles: List[str],
        locations: List[str],
        company_employee_counts: List[str]
    ) -> Optional[List[Dict]]:
        """
        A mock version of search_people that returns hardcoded data
        MATCHING THE OFFICIAL API DOCUMENTATION.
        """
        print("\n⚠️  WARNING: Using MOCK data for search_people. Not a live API call. ⚠️\n")
        
        mock_response = {
            "contacts": [
                {
                    "id": "mock_contact_12345",
                    "name": "Aaryan Sharma",
                    "first_name": "Aaryan",
                    "last_name": "Sharma",
                    "title": "Founder & Lead Developer",
                    "email_status": "verified",
                    "linkedin_url": "http://www.linkedin.com/in/aaryansharma",
                    "email": "aaryan.sharma@hyperion.agency",
                    "organization": {
                        "id": "mock_org_67890",
                        "name": "Hyperion Agency",
                        "website_url": "http://www.hyperion.agency",
                        "primary_domain": "hyperion.agency"
                    }
                },
                {
                    "id": "mock_contact_67890",
                    "name": "Jane Doe",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "title": "VP of Engineering",
                    "email_status": "verified",
                    "linkedin_url": "http://www.linkedin.com/in/janedoe",
                    "email": "jane.doe@examplecorp.com",
                    "organization": {
                        "id": "mock_org_abcde",
                        "name": "ExampleCorp",
                        "website_url": "http://www.examplecorp.com",
                        "primary_domain": "examplecorp.com"
                    }
                }
            ],
            "pagination": { "page": 1, "per_page": 2, "total_entries": 2, "total_pages": 1 }
        }
        return mock_response.get('contacts', [])