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
from src.hyperion.config import PROJECT_ROOT

def load_prompt(file_name: str) -> str:
    """Loads a prompt template from the prompts directory."""
    prompt_path = PROJECT_ROOT / "src" / "hyperion" / "prompts" / file_name
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()

class AgentState(TypedDict):
    prospect: Dict
    queries: Optional[List[str]]
    website_context: Optional[str]
    search_results: Optional[List[Dict]]
    summaries: Optional[List[str]]
    hook: Optional[str]
    max_retries: int
    retries: int
    source_url: Optional[str]

def scrape_website_for_context(state: AgentState) -> Dict:
    """
    Node: Scrapes the prospect's company website for initial context.
    """

    print("\n--- Node: Scraping Website for Context ---")
    
    try:
        website_url = state['prospect'].get('organization', {}).get('primary_domain')
        if not website_url:
            print("  - No website URL found. Returning empty context.")
            return {"website_context": "No website data available."}

        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url

        firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
        app = FirecrawlApp(api_key=firecrawl_api_key)
        scraped_data = app.scrape(website_url)

        if not scraped_data or not scraped_data.markdown:
            print("  - FireCrawl failed to extract content. Returning empty context.")
            return {"website_context": "Failed to retrieve website data."}
        
        content = scraped_data.markdown
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"Summarize what this company does in one single, concise sentence based on their website content:\n\n{content[:10000]}"
        response = model.generate_content(prompt)
        summary = response.text.strip()
        
        print(f"  - Website Context Found: {summary}")
        return {"website_context": summary}

    except Exception as e:
        print(f"  - An error occurred during context scraping: {e}")
        return {"website_context": f"An error occurred: {e}"}


def generate_search_queries(state: AgentState) -> Dict:
    """
    Node: Now uses website context to generate better queries.
    """
    prospect = state['prospect']
    website_context = state['website_context']
    prospect_name = prospect.get('name', '')
    company_name = prospect.get('organization', {}).get('name', '')

    print(f"\n--- Node: Generating Search Queries (with context) ---")
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = (
        f"You are a research analyst. You are researching a person named '{prospect_name}' at a company called '{company_name}'.\n"
        f"Here is a summary of what the company does: '{website_context}'\n\n"
        "Based on this, generate 3 highly specific and relevant Google search queries to find a recent, personalized 'hook'. "
        "Focus on finding news, recent projects, or achievements related to their specific industry.\n"
        "Return your response as a JSON-formatted list of strings."
    )
    
    response = model.generate_content(prompt)
    json_response = response.text.strip().replace("```json\n", "").replace("\n```", "")
    queries = json.loads(json_response)
    
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
    Node: A tiered scraper with the FINAL FireCrawl logic.
    """
    search_results = state['search_results']
    print("\n--- Node: Scraping and Summarizing (Tiered Method) ---")
    summaries = []
    urls = [result.get('link') for result in search_results[:3]]
    firecrawl_app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    
    for url in urls:
        if not url: continue
        print(f"Scraping: {url}")
        content = ""
        try:
            if url.lower().endswith('.pdf'):
                headers = {'User-Agent': 'Mozilla/5.0...'}
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                reader = PdfReader(io.BytesIO(response.content))
                content = " ".join(page.extract_text() for page in reader.pages)
            else:
                scraped_data = firecrawl_app.scrape(url)
                if scraped_data and scraped_data.markdown:
                    content = scraped_data.markdown
                else:
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
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = f"Summarize the following text in 2-3 sentences:\n\n{content[:15000]}"
                summaries.append(model.generate_content(prompt).text)
            else:
                print("  - All scraping methods failed.")

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

# def build_agent_graph():
#     """Builds the upgraded LangGraph agent with the new context node."""
#     load_dotenv()
#     google_api_key = os.getenv("GOOGLE_API_KEY")
#     genai.configure(api_key=google_api_key)

#     graph = StateGraph(AgentState)

#     # Add all nodes, including the new one
#     graph.add_node("scrape_website_for_context", scrape_website_for_context)
#     graph.add_node("generate_queries", generate_search_queries)
#     graph.add_node("web_search", execute_web_search)
#     graph.add_node("scrape_and_summarize", scrape_and_summarize_content)
#     graph.add_node("synthesize_hook", synthesize_hook)
#     graph.add_node("prepare_for_retry", prepare_for_retry)

#     # --- New Graph Structure ---
#     graph.set_entry_point("scrape_website_for_context")
#     graph.add_edge("scrape_website_for_context", "generate_queries") # New first step
#     graph.add_edge("generate_queries", "web_search")
#     graph.add_edge("web_search", "scrape_and_summarize")
#     graph.add_edge("scrape_and_summarize", "synthesize_hook")
    
#     graph.add_conditional_edges(
#         "synthesize_hook",
#         should_continue,
#         {"retry": "prepare_for_retry", "end": END}
#     )
#     graph.add_edge("prepare_for_retry", "web_search")

#     return graph.compile()

def build_agent_graph():
    """Builds the simplified, more reliable 'Website-First' agent."""
    load_dotenv()
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

    graph = StateGraph(AgentState)
    graph.add_node("scrape_website", scrape_website)
    graph.add_node("synthesize_hook_from_website", synthesize_hook_from_website)

    graph.set_entry_point("scrape_website")
    graph.add_edge("scrape_website", "synthesize_hook_from_website")
    graph.add_edge("synthesize_hook_from_website", END)

    return graph.compile()

# def generate_email(prospect: Dict, hook: str) -> Optional[str]:
#     """
#     Uses Gemini 2.5 Pro to generate a complete, personalized outreach email
#     by loading and formatting an external prompt template.
#     """
#     print("\n--- Node: Generating Final Email (from template) ---")
#     try:
#         load_dotenv()
#         agency_name = os.getenv("AGENCY_NAME")
#         agency_value_prop = os.getenv("AGENCY_VALUE_PROP")

#         if not agency_name or not agency_value_prop:
#             raise ValueError("AGENCY_NAME or AGENCY_VALUE_PROP not set in .env file.")

#         prospect_first_name = prospect.get('name', '').split(' ')[0]
        
#         prompt_template = load_prompt("generate_email.md")
        
#         prompt = prompt_template.format(
#             prospect_first_name=prospect_first_name,
#             prospect_title=prospect.get('title', 'a key leader'),
#             company_name=prospect.get('organization', {}).get('name', ''),
#             hook=hook,
#             your_agency_name=agency_name,
#             your_agency_value_prop=agency_value_prop
#         )
        
#         google_api_key = os.getenv("GOOGLE_API_KEY")
#         if not google_api_key:
#             raise ValueError("GOOGLE_API_KEY not found.")
#         genai.configure(api_key=google_api_key)
        
#         model = genai.GenerativeModel('gemini-2.5-pro')
#         response = model.generate_content(prompt)
#         print("  - Successfully generated email from upgraded template.")
#         return response.text.strip()

#     except Exception as e:
#         print(f"  - An error occurred during email generation: {e}")
#         return None

def scrape_website(state: AgentState) -> Dict:
    """
    Node: Scrapes the website and returns both the content and the source URL.
    """

    print("\n--- Node: Scraping Website for Hook Generation ---")
    content = "No website data available."
    url = "N/A"
    try:
        prospect = state['prospect']
        website_url = prospect.get('organization', {}).get('primary_domain')
        if not website_url: raise ValueError("No website URL found.")

        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url
        url = website_url

        app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
        scraped_data = app.scrape(url)

        if scraped_data and scraped_data.markdown:
            content = scraped_data.markdown
            print("  - Successfully scraped website content.")
            print(f"\n Scraped data: \n {content}")
        else:
            raise ValueError("FireCrawl failed to extract markdown content.")

    except Exception as e:
        print(f"  - An error occurred during website scraping: {e}")
        content = f"An error occurred during scraping: {e}"

    return {"website_content": content, "source_url": url}

def synthesize_hook_from_website(state: AgentState) -> Dict:
    """
    Node: Uses website content and a new, more advanced prompt to create a high-quality hook.
    """

    print("\n--- Node: Synthesizing Hook from Website (v2) ---")
    website_content = state.get('website_content', '')
    prospect = state.get('prospect', {})
    
    if "error" in website_content.lower() or "failed" in website_content.lower():
        return {"hook": None}

    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        prompt_template = load_prompt("synthesize_hook_from_website.md")
        prospect_first_name = prospect.get('name', '').split(' ')[0]
        prospect_title = prospect.get('title', 'a key leader')
        company_name = prospect.get('organization', {}).get('name', '')
        prompt = prompt_template.format(
            prospect_first_name=prospect_first_name,
            prospect_title=prospect_title,
            company_name=company_name,
            website_content=website_content[:12000]
        )
        
        response = model.generate_content(prompt)
        # We take the last line of the response, as the model might do some chain-of-thought first
        hook = response.text.strip().split('\n')[-1].replace("Generated Hook:", "").strip()
        
        print(f"  - Synthesized Hook: {hook}")
        return {"hook": hook}
    except Exception as e:
        print(f"  - An error occurred during hook synthesis: {e}")
        return {"hook": None}

def generate_email(prospect: Dict, hook: str) -> Optional[str]:
    """Uses Gemini 2.5 Pro and an external template to generate the final email."""
    print("\n--- Node: Generating Final Email (from template) ---")
    try:
        load_dotenv()
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        
        prompt_template = load_prompt("generate_email.md")
        prompt = prompt_template.format(
            prospect_first_name=prospect.get('name', '').split(' ')[0],
            prospect_title=prospect.get('title', 'a key leader'),
            company_name=prospect.get('organization', {}).get('name', ''),
            hook=hook,
            your_agency_name=os.getenv("AGENCY_NAME"),
            your_agency_value_prop=os.getenv("AGENCY_VALUE_PROP")
        )
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(prompt)
        print("  - Successfully generated email from upgraded template.")
        return response.text.strip()
    except Exception as e:
        print(f"  - An error occurred during email generation: {e}")
        return None