import os
import json
import requests
from dotenv import load_dotenv
from typing import List, Dict, Optional
import google.generativeai as genai
from newspaper import Article

def execute_web_search(query: str) -> Optional[List[Dict]]:
    """
    Executes a web search for a given query using Serper API.

    Args:
        query: The search query string.

    Returns:
        A list of dictionaries representing the organic search results,
        or None if an error occurs.
    """

    load_dotenv()
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        raise ValueError("ERROR: SERPER_API_KEY not found in environment variables.")
    
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query})
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    print(f"Executing search for: '{query}'...")

    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()

        data = response.json()

        return data.get('organic', [])
    
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")

    except Exception as err:
        print(f"An other error occurred: {err}")

    return None

def scrape_and_summarize_content(url: str) -> Optional[str]:
    """
    Scrapes the content of a URL and uses Gemini 2.5 Flash to summarize it.

    Args:
        url: The URL to scrape and summarize.

    Returns:
        A concise summary of the article's content, or None if an error occurs.
    """

    print(f"\n Scraping and summarizing URL: {url}")

    try:
        article = Article(url)
        article.download()
        article.parse()

        if not article.text:
            print("Failed to extract article text.")
            return None
        
        print("Successfully extracted article text.")

        load_dotenv()
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("ERROR: GOOGLE_API_KEY not found in environment variables.")
        
        genai.configure(api_key=google_api_key)

        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = (
            "You are a world-class business intelligence analyst. Your task is to read the following article text "
            "and provide a concise, 2-3 sentence summary that would be useful for a sales executive looking for a personalized "
            "email hook. Focus on the core announcement, key figures, or the main strategic point of the article.\n\n"
            f"Article Text:\n---\n{article.text[:4000]}"
        )

        response = model.generate_content(prompt)

        print("Successfully generated summary with Gemini.")

        return response.text
    
    except Exception as e:
        print(f"An error occurred during scraping or summarization: {e}")
        return None
    
def generate_search_queries(prospect: Dict) -> Optional[List[str]]:
    """
    Uses Gemini 2.5 Flash to generate a list of effective search queries for a prospect.

    Args:
        prospect: A dictionary containing prospect information (e.g., name, organization.)

    Returns:
        A list of search query strings, or None if an error occurs.
    """

    prospect_name = prospect.get('name')
    company_name = prospect.get('organization', {}).get('name', '')

    if not prospect_name or not company_name:
        print("Error: Prospect name or company name is missing.")
        return None
    
    print(f"\n Generating search queries for {prospect_name} at {company_name}...")

    try:
        load_dotenv()
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("ERROR: GOOGLE_API_KEY not found in the environment variables.")
        genai.configure(api_key=google_api_key)

        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = (
            "You are a world-class Sales Development Representative (SDR) and research analyst. "
            f"You have been given a prospect's name, '{prospect_name}', and their company, '{company_name}'.\n"
            "Your goal is to generate 3 to 5 diverse and insightful Google search queries to find a recent, personalized 'hook' for a cold email. "
            "Good queries are about recent company news, funding rounds, product launches, executive keynotes, or personal achievements.\n"
            "Bad queries are generic searches for the company homepage or the person's LinkedIn profile.\n"
            "Return your response as a JSON-formatted list of strings. For example: "
            '["query 1", "query 2", "query 3"]'
        )

        response = model.generate_content(prompt)

        json_response = response.text.strip().replace("```json\n", "").replace("\n```", "")

        queries = json.loads(json_response)

        print(f" - Successfully generated search queries.")

        return queries
    
    except Exception as e:
        print(f"An error occurred during query generation: {e}")
        return None