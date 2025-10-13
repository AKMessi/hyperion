import os
import json
import requests
from dotenv import load_dotenv
from typing import List, Dict, Optional, TypedDict
import google.generativeai as genai
from newspaper import Article
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from firecrawl import FirecrawlApp
import io
from pypdf import PdfReader

class AgentState(TypedDict):
    prospect: Dict
    queries: Optional[List[str]]
    search_results: Optional[List[Dict]]
    summaries: Optional[List[str]]
    hook: Optional[str]
    max_retries: int
    retries: int

def generate_search_queries(state: AgentState) -> Dict:
    """
    Node: Generates search queries based on the prospect.
    """

    prospect = state['prospect']
    prospect_name = prospect.get('name')
    company_name = prospect.get('organization', {}).get('name', '')

    if not prospect_name or not company_name:
        print("Error: Prospect name or company name is missing.")
        return None
    
    print(f"\n Generating search queries for {prospect_name} at {company_name}...")

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
    print(f"Generated Queries: {queries}")

    return {"queries": queries, "retries": 0}

def execute_web_search(state: AgentState) -> Dict:
    """
    Node: Executes a web search for the generated queries.
    """

    queries = state['queries']
    print("\n--- Node: Executing Web Search ---")
    
    top_query = queries[0]
    print(f"Searching for: '{top_query}'")

    api_key = os.getenv("SERPER_API_KEY")
    url = "https://google.serper.dev/search"

    payload = json.dumps({"q": top_query})
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    data = response.json()
    
    return {"search_results": data.get('organic', [])}

def scrape_and_summarize_content(state: AgentState) -> Dict:
    """
    Node: A tiered scraper that tries multiple methods to extract and summarize content.
    1. Handles PDFs using pypdf.
    2. Tries FireCrawl for JavaScript-heavy sites.
    3. Falls back to a simple requests+newspaper3k for basic articles.
    """
    search_results = state['search_results']
    print("\n--- Node: Scraping and Summarizing (Tiered Method) ---")

    summaries = []
    urls_to_scrape = [result.get('link') for result in search_results[:3]]
    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")

    if not firecrawl_api_key:
        raise ValueError("ERROR: FIRECRAWL_API_KEY not found.")

    firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
    
    for url in urls_to_scrape:
        if not url: continue
        
        print(f"Scraping: {url}")
        content = ""

        try:
            # method 1: Handle PDFs
            if url.lower().endswith('.pdf'):
                print("  - Detected PDF. Using pypdf...")
                headers = {'User-Agent': 'Mozilla/5.0...'}

                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                reader = PdfReader(io.BytesIO(response.content))
                content = " ".join(page.extract_text() for page in reader.pages)

            else:
                # method 2: Try FireCrawl first
                print("  - Attempting FireCrawl...")
                scraped_data = firecrawl_app.scrape(url)
                
                if scraped_data and isinstance(scraped_data, list) and scraped_data[0] and 'markdown' in scraped_data[0]:
                    content = scraped_data[0]['markdown']

                else:
                    # method 3: Fallback to requests + newspaper3k
                    print("  - FireCrawl failed. Falling back to newspaper3k...")
                    headers = {'User-Agent': 'Mozilla/5.0...'}

                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()

                    article = Article(url)
                    article.html = response.text

                    article.parse()
                    content = article.text

            if content:
                print("  - Successfully extracted content.")

                # summarize the extracted content with Gemini
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = f"Summarize the following text in 2-3 sentences, focusing on the core message:\n\n{content[:15000]}"
                
                summary_response = model.generate_content(prompt)
                summaries.append(summary_response.text)

            else:
                print("  - All scraping methods failed to extract content.")

        except Exception as e:
            print(f"  - An error occurred: {e}")
    
    return {"summaries": summaries}

def synthesize_hook(state: AgentState) -> Dict:
    """
    Node: Synthesizes a personalized hook from the summaries.
    """

    summaries = state['summaries']
    prospect = state['prospect']
    prospect_name = prospect.get('name', '')

    print("\n--- Node: Synthesizing Hook ---")

    if not summaries:
        print("No summaries to synthesize from.")
        return {"hook": None}

    full_summary = "\n\n".join(summaries)
    
    model = genai.GenerativeModel('gemini-2.5-pro')

    prompt = (
        "You are an expert-level Sales Development Representative. Your task is to write a single, compelling, personalized sentence to use as a 'hook' in a cold email. "
        f"You will be given a collection of summaries from recent news articles. Your hook should directly reference the most interesting piece of information and feel personal to the recipient, '{prospect_name}'.\n"
        "Rules:\n1. Must be a single sentence.\n2. Must be concise and sound natural.\n3. Must NOT be a question.\n\n"
        f"Use the following summaries to generate a hook for {prospect_name}:\n\n"
        f"Summaries:\n---\n{full_summary}"
    )
    response = model.generate_content(prompt)
    hook = response.text.strip().replace('"', '')
    
    print(f"Synthesized Hook: {hook}")
    return {"hook": hook}

def should_continue(state: AgentState) -> str:
    """
    Edge: Decides whether to try again or end the process.
    """

    print("\n Edge: Evaluating Hook")
    hook = state.get('hook')
    retries = state.get('retries', 0)
    max_retries = state.get('max_retries', 1)

    if hook and "not find" not in hook.lower() and "no relevant" not in hook.lower():
        print("Evaluation: Hook is good. Ending the process.")
        return "end"
    
    else:
        print(f"Evaluation: Hook is not good. Retries: {retries}/{max_retries}")
        if retries < max_retries:
            return "retry"
        else:
            print("Evaluation: Max retries reached. Ending process.")
            return "end"
        
def prepare_for_retry(state:AgentState) -> Dict:
    """
    Node: Increments retry counter and clears old data for a new attempt.
    """

    print("\n --- Node: Preparing for retry ---")
    retries = state.get('retries', 0) + 1
    queries = state['queries'][1:]

    return {
        "queries": queries,
        "retries": retries,
        "search_results": None,
        "summaries": None,
        "hook": None
    }

# building the agent graph

def build_agent_graph():
    """
    Builds the LangGraph agent.
    """

    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=google_api_key)

    graph = StateGraph(AgentState)

    graph.add_node("generate_queries", generate_search_queries)
    graph.add_node("web_search", execute_web_search)
    graph.add_node("scrape_and_summarize", scrape_and_summarize_content)
    graph.add_node("synthesize_hook", synthesize_hook)
    graph.add_node("prepare_for_retry", prepare_for_retry)

    graph.set_entry_point("generate_queries")

    graph.add_edge("generate_queries", "web_search")
    graph.add_edge("web_search", "scrape_and_summarize")
    graph.add_edge("scrape_and_summarize", "synthesize_hook")

    graph.add_conditional_edges(
        "synthesize_hook",
        should_continue,
        {
            "retry": "prepare_for_retry",
            "end": END
        }
    )
    graph.add_edge("prepare_for_retry", "web_search")

    return graph.compile()