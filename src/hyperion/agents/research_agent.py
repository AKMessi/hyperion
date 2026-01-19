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
from tavily import TavilyClient
from google.generativeai import types

def safe_gemini_generate(model, prompt, context_name="Unknown"):
    """
    Safely calls Gemini with comprehensive error handling.
    Returns: (success: bool, text: str, error_msg: str)
    """
    try:
        response = model.generate_content(prompt)
        
        # Check if response exists
        if not response:
            return False, "", f"{context_name}: No response object returned"
        
        # Check for prompt feedback (blocked before generation)
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            if hasattr(response.prompt_feedback, 'block_reason'):
                return False, "", f"{context_name}: Prompt blocked - {response.prompt_feedback.block_reason}"
        
        # Check if candidates exist
        if not response.candidates or len(response.candidates) == 0:
            return False, "", f"{context_name}: No candidates returned"
        
        candidate = response.candidates[0]
        
        # Check finish reason
        finish_reasons = {
            0: "UNSPECIFIED",
            1: "STOP",  # This is actually success
            2: "MAX_TOKENS",
            3: "SAFETY",
            4: "RECITATION",
            5: "OTHER"
        }
        
        finish_reason_name = finish_reasons.get(candidate.finish_reason, "UNKNOWN")
        
        # If not STOP, something went wrong
        if candidate.finish_reason != 1:
            error_details = f"Finish reason: {finish_reason_name}"
            if hasattr(candidate, 'safety_ratings'):
                error_details += f", Safety: {candidate.safety_ratings}"
            return False, "", f"{context_name}: {error_details}"
        
        # Check if content parts exist
        if not candidate.content or not candidate.content.parts:
            return False, "", f"{context_name}: No content parts (finish_reason was STOP but no content)"
        
        # Extract text
        text = response.text.strip()
        
        if not text:
            return False, "", f"{context_name}: Empty text returned"
        
        return True, text, ""
        
    except AttributeError as e:
        return False, "", f"{context_name}: Attribute error - {str(e)}"
    except Exception as e:
        return False, "", f"{context_name}: Exception - {str(e)}"

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
    research_question: Optional[str]
    research_summary: Optional[str]
    company_research: Optional[str]
    person_research: Optional[str]

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
        model = genai.GenerativeModel('gemini-3-flash-preview')
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
    model = genai.GenerativeModel('gemini-3-flash-preview')
    
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
                model = genai.GenerativeModel('gemini-3-flash-preview')
                prompt = f"Summarize the following text in 2-3 sentences:\n\n{content[:15000]}"
                summaries.append(model.generate_content(prompt).text)
            else:
                print("  - All scraping methods failed.")

        except Exception as e:
            print(f"  - An error occurred: {e}")
    
    return {"summaries": summaries}

def synthesize_final_hook(state: AgentState) -> Dict:
    """
    FINAL Node: The 'Selector' that chooses the best hook from all available intelligence.
    """
    print("\n--- Node: 4. Synthesizing Final Hook ---")
    
    person_research = state.get('person_research', '')
    company_research = state.get('company_research', '') 
    prospect = state.get('prospect', {})
    
    try:
        model = genai.GenerativeModel(
            'gemini-3-flash-preview',
            safety_settings={
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        prompt_template = load_prompt("synthesize_hook_from_website.md")
        prompt = prompt_template.format(
            person_research=person_research,
            company_research=company_research,
            prospect_first_name=prospect.get('name', '').split(' ')[0]
        )
        
        # Use the safe wrapper
        success, hook, error = safe_gemini_generate(model, prompt, "synthesize_final_hook")
        
        if not success:
            print(f"  - ❌ Failed to generate hook: {error}")
            # Fallback: create a simple hook from company name
            company_name = prospect.get('organization', {}).get('name', 'your company')
            hook = f"I noticed {company_name}'s recent growth."
            print(f"  - Using fallback hook: {hook}")
        else:
            print(f"  - ✅ Final Synthesized Hook: {hook}")
        
        return {"hook": hook}
        
    except Exception as e:
        print(f"  - ❌ Exception in synthesize_final_hook: {e}")
        company_name = prospect.get('organization', {}).get('name', 'your company')
        fallback_hook = f"I noticed {company_name}'s recent growth."
        return {"hook": fallback_hook}

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

# def build_agent_graph():
#     """
#     Builds the simplified, more reliable 'Website-First' agent.
#     """

#     load_dotenv(); genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
#     graph = StateGraph(AgentState)
#     graph.add_node("scrape_website", scrape_website)
#     graph.add_node("synthesize_hook_from_website", synthesize_hook_from_website)
#     graph.set_entry_point("scrape_website")
#     graph.add_edge("scrape_website", "synthesize_hook_from_website")
#     graph.add_edge("synthesize_hook_from_website", END)

#     return graph.compile()

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

def scrape_company_website(state: AgentState) -> Dict:
    """
    Node: The reliable fallback scraper for company-centric hooks.
    """

    print("\n--- Node: Fallback - Scraping Company Website ---")
    content, url = "No data available.", "N/A"
    try:
        website_url = state['prospect']['organization']['primary_domain']
        if not website_url.startswith(('http://', 'https://')):
            website_url = 'https://' + website_url
        url = website_url
        app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
        scraped_data = app.scrape(url)
        if scraped_data and scraped_data.markdown:
            content = scraped_data.markdown
            print("  - Successfully scraped website markdown.")
        else:
            raise ValueError("FireCrawl failed on website scrape.")
    except Exception as e:
        print(f"  - An error occurred during website scrape: {e}")
        content = f"Error: {e}"

    return {"company_research": content, "source_url": url}

def synthesize_hook_from_website(state: AgentState) -> Dict:
    """
    Node: Uses website content and a new, more advanced prompt to create a high-quality hook.
    """

    print("\n--- Node: Synthesizing Hook from Website (v6) ---")
    raw_website_content = state.get('website_content', '')
    prospect = state.get('prospect', {})
    
    if "error" in raw_website_content.lower() or "failed" in raw_website_content.lower():
        return {"hook": None}

    try:
        model = genai.GenerativeModel('gemini-3-flash-preview')
        prompt_template = load_prompt("synthesize_hook_from_website.md")
        prospect_first_name = prospect.get('name', '').split(' ')[0]
        prospect_title = prospect.get('title', 'a key leader')
        company_name = prospect.get('organization', {}).get('name', '')
        prompt = prompt_template.format(
            prospect_first_name=prospect_first_name,
            prospect_title=prospect_title,
            company_name=company_name,
            raw_website_content=raw_website_content[:12000]
        )
        
        response = model.generate_content(prompt)
        # we take the last line of the response, as the model might do some chain-of-thought first
        hook = response.text.strip().split('\n')[-1].replace("Generated Hook:", "").strip()
        
        print(f"  - Synthesized Hook: {hook}")
        return {"hook": hook}
    except Exception as e:
        print(f"  - An error occurred during hook synthesis: {e}")
        return {"hook": None}

def generate_email(prospect: Dict, hook: str, state: AgentState) -> Optional[str]:
    """Uses Gemini 2.5 Pro and an external template to generate the final email."""
    print("\n--- Node: Generating Final Email (from template) ---")
    try:
        load_dotenv()
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

        website_content = state.get('company_research', '')
        
        # Load the template
        prompt_template = load_prompt("generate_email.md")
        
        # Extract variables
        prospect_first_name = prospect.get('name', '').split(' ')[0]
        prospect_title = prospect.get('title', 'a key leader')
        company_name = prospect.get('organization', {}).get('name', '')
        agency_name = os.getenv("AGENCY_NAME", "Get AI Simplified")
        agency_value_prop = os.getenv("AGENCY_VALUE_PROP", "We build autonomous AI agents")
        
        # Replace variables safely
        prompt = prompt_template
        prompt = prompt.replace('{prospect_first_name}', prospect_first_name)
        prompt = prompt.replace('{prospect_title}', prospect_title)
        prompt = prompt.replace('{company_name}', company_name)
        prompt = prompt.replace('{hook}', hook)
        prompt = prompt.replace('{website_content}', website_content[:10000])
        prompt = prompt.replace('{your_agency_name}', agency_name)
        prompt = prompt.replace('{your_agency_value_prop}', agency_value_prop)
        
        # Configure model with ALL safety settings off
        model = genai.GenerativeModel(
            'gemini-3-flash-preview',
            safety_settings={
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        response = model.generate_content(prompt)
        
        # Detailed error checking
        if not response.candidates:
            print(f"  - ❌ No candidates returned")
            print(f"  - Prompt feedback: {response.prompt_feedback}")
            return None
        
        candidate = response.candidates[0]
        
        if candidate.finish_reason != 1:  # 1 = STOP (success)
            finish_reasons = {
                0: "FINISH_REASON_UNSPECIFIED",
                1: "STOP",
                2: "MAX_TOKENS",
                3: "SAFETY",
                4: "RECITATION",
                5: "OTHER"
            }
            reason = finish_reasons.get(candidate.finish_reason, "UNKNOWN")
            print(f"  - ❌ Generation blocked: {reason}")
            print(f"  - Safety ratings: {candidate.safety_ratings}")
            
            # If blocked by safety, try with a simpler prompt
            if candidate.finish_reason == 3:
                print(f"  - Attempting fallback email generation...")
                return generate_fallback_email(prospect, hook)
            
            return None
        
        if not candidate.content.parts:
            print(f"  - ❌ No content parts in response")
            return None
        
        email_text = response.text.strip()
        print("  - ✅ Successfully generated email")
        return email_text
        
    except Exception as e:
        print(f"  - ❌ Exception during email generation: {e}")
        print(f"  - Attempting fallback email generation...")
        return generate_fallback_email(prospect, hook)


def generate_fallback_email(prospect: Dict, hook: str) -> str:
    """
    Generates a basic but effective email when the AI generation fails.
    This ensures the system never fully fails.
    """
    print("  - Using fallback email template...")
    
    prospect_first_name = prospect.get('name', '').split(' ')[0]
    company_name = prospect.get('organization', {}).get('name', '')
    
    # Simple, proven email template
    subject = f"quick question about {company_name}"
    
    body = f"""Hi {prospect_first_name},

    {hook}

    That got me thinking about how much manual work goes into finding insights like this. I built an AI agent that does this research automatically - it's how I found yours.

    Curious if you're exploring AI for any similar workflows?

    Best,
    Aaryan"""
    
    return f"Subject: {subject}\n\n{body}"
    

def generate_research_question(state: AgentState) -> Dict:
    """
    Generates a CONCISE research question for Tavily.
    """
    print("\n--- Node: 1. Generating Research Question ---")
    prospect = state['prospect']
    prospect_name = prospect.get('name', '')
    company_name = prospect.get('organization', {}).get('name', '')
    
    prompt = (
        "You are an expert research analyst. Generate a single, concise search query. "
        f"Find a personalized hook for '{prospect_name}' from '{company_name}'.\n"
        "Focus on recent news, achievements, or public statements.\n"
        "Output: Single question or search phrase only. No explanation."
    )
    
    model = genai.GenerativeModel(
        'gemini-3-flash-preview',
        safety_settings={
            genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        }
    )
    
    success, question, error = safe_gemini_generate(model, prompt, "generate_research_question")
    
    if not success:
        print(f"  - ❌ Failed: {error}")
        question = f"recent news about {prospect_name} at {company_name}"
        print(f"  - Using fallback query: {question}")
    else:
        if len(question) > 400:
            question = question[:399]
        print(f"  - ✅ Generated Question: {question}")
    
    return {"research_question": question}
    
def execute_tavily_research(state: AgentState) -> Dict:
    """Executes a search query using the Tavily API with robust error handling."""
    print("\n--- Node: 2. Executing Tavily Research ---")
    query = state.get("research_question")
    
    summary = f"Failed to execute Tavily search for query: {query}"
    source_url = "N/A"

    if not query or "Error:" in query:
        summary = "Failed to generate a valid research question."
    else:
        try:
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                raise ValueError("TAVILY_API_KEY not found in environment. Please check your .env file.")
            
            tavily_client = TavilyClient(api_key=api_key)
            
            response = tavily_client.search(query=query, search_depth="advanced")

            if response and response.get('answer'):
                summary = response.get('answer')
                print(f"  - Tavily Answer Found: {summary[:200]}...")
                results = response.get('results')
                if results and isinstance(results, list) and len(results) > 0:
                    source_url = results[0].get('url', 'N/A')
            else:
                summary = "Tavily search returned no answer."
                print("  - Tavily search completed but returned no direct answer.")

        except Exception as e:
            print(f"  - An error occurred during Tavily search: {e}")
            summary = f"An error occurred during Tavily search: {e}"
            
    return {"research_summary": summary, "source_url": source_url}
    
def synthesize_hook_from_tavily(state: AgentState) -> Dict:
    """
    Uses the Tavily research summary to create a hook.
    """
    print("\n--- Node: 3. Synthesizing Hook (from Tavily) ---")
    research_summary = state.get('research_summary', '')
    prospect = state.get('prospect', {})
    
    if "Error:" in research_summary or "Failed" in research_summary:
        print(f"  - Invalid research summary: {research_summary}")
        return {"hook": "No compelling hook found."}
    
    try:
        model = genai.GenerativeModel(
            'gemini-3-flash-preview',
            safety_settings={
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }
        )

        prompt_template = load_prompt("synthesize_hook_from_tavily.md")
        prompt = prompt_template.format(
            prospect_first_name=prospect.get('name', '').split(' ')[0],
            research_summary=research_summary
        )
        
        success, hook, error = safe_gemini_generate(model, prompt, "synthesize_hook_from_tavily")
        
        if not success:
            print(f"  - ❌ Failed: {error}")
            hook = "No compelling hook found."
        else:
            print(f"  - ✅ Synthesized Hook: {hook}")
        
        return {"hook": hook}
        
    except Exception as e:
        print(f"  - ❌ Exception: {e}")
        return {"hook": "No compelling hook found."}
    
def should_fallback_to_website(state: AgentState) -> str:
    """
    Edge: Checks if Tavily failed. If so, routes to website scrape.
    """

    print("\n--- Edge: Evaluating Tavily Result ---")
    person_research = state.get('person_research', '')
    
    if "Error" in person_research or "Failed" in person_research or "No direct answer" in person_research or not person_research:
        print("  - Tavily failed or empty. Falling back to company website scrape.")
        return "fallback_to_website"
    else:
        print("  - Tavily succeeded. Proceeding to hook synthesis.")
        
        state['company_research'] = ""
        return "continue_to_synthesis"

def synthesize_final_hook(state: AgentState) -> Dict:
    """
    FINAL Node: The 'Selector' that chooses the best hook from all available intelligence.
    """

    print("\n--- Node: 4. Synthesizing Final Hook ---")
    person_research = state.get('person_research', '')
    company_research = state.get('company_research', '') 
    prospect = state.get('prospect', {})
    hook = "No compelling hook found."
    try:
        model = genai.GenerativeModel('gemini-3-flash-preview')
        prompt_template = load_prompt("synthesize_hook_from_website.md")
        prompt = prompt_template.format(
            person_research=person_research,
            company_research=company_research,
            prospect_first_name=prospect.get('name', '').split(' ')[0]
        )
        safety_settings = {'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE', 'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE', 'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE', 'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'}
        response = model.generate_content(prompt, safety_settings=safety_settings)
        hook = response.text.strip()
        print(f"  - Final Synthesized Hook: {hook}")
    except Exception as e:
        print(f"  - An error occurred during final synthesis: {e}")
    return {"hook": hook}
    
def build_agent_graph():
    """
    Builds the final, Dual-Pronged agent graph.
    """

    load_dotenv(); genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    graph = StateGraph(AgentState)

    graph.add_node("generate_research_question", generate_research_question)
    graph.add_node("execute_tavily_research", execute_tavily_research)
    graph.add_node("scrape_company_website", scrape_company_website)
    graph.add_node("synthesize_final_hook", synthesize_final_hook)

    graph.set_entry_point("generate_research_question")
    graph.add_edge("generate_research_question", "execute_tavily_research")

    graph.add_conditional_edges(
        "execute_tavily_research",
        should_fallback_to_website,
        {
            "fallback_to_website": "scrape_company_website",
            "continue_to_synthesis": "synthesize_final_hook"
        }
    )

    graph.add_edge("scrape_company_website", "synthesize_final_hook")
    graph.add_edge("synthesize_final_hook", END)

    return graph.compile()