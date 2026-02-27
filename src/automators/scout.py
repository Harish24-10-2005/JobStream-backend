import asyncio
import requests
from typing import List, Set, Optional
from pydantic import BaseModel, Field
from langchain_community.utilities import SerpAPIWrapper
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from src.automators.base import BaseAgent
from src.core.console import console

# ============================================
# Pydantic Schemas for Strict Output Parsing
# ============================================
class ScrapedJob(BaseModel):
    url: str
    source_domain: str
    status: str = Field(default="discovered", description="Current status: discovered, applied, failed, skipped")
    query_matched: str = Field(default="", description="The query that found this job")

class ScoutAgent(BaseAgent):
    """
    Agent responsible for finding job listings.
    """
    def __init__(self):
        super().__init__()
        # Initialize SerpAPI with key from secure settings
        key = self.settings.serpapi_api_key.get_secret_value()
        if not key:
            self.logger.error("ScoutAgent: SERPAPI_API_KEY is missing or empty!")
            raise ValueError("SERPAPI_API_KEY is required for ScoutAgent")
            
        self.logger.debug(f"ScoutAgent: Initializing SerpAPI with key length {len(key)}")
        
        self.search = SerpAPIWrapper(
            serpapi_api_key=key,
            params={
                "engine": "google",
                "google_domain": "google.com", 
                "gl": "us", 
                "hl": "en",
                "num": 20
            }
        )
        # Initialize LLM for Reflection/Self-Correction
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            api_key=self.settings.groq_api_key.get_secret_value()
        )
        
        self.ats_domains = ["site:greenhouse.io", "site:lever.co", "site:ashbyhq.com"]
        self.valid_domains = ["greenhouse.io", "lever.co", "ashbyhq.com"]

    async def run(self, query: str, location: str = "", freshness: str = "month", attempt: int = 1, webhook_url: Optional[str] = None) -> List[ScrapedJob]:
        """
        Searches for jobs targeting ATS domains.
        freshness: 'day' | 'week' | 'month' | None
        attempt: current retry attempt (max 2)
        webhook_url: optional URL to POST results to instantly
        """
        # Map freshness to Google Time-Based Search (tbs) params
        tbs_map = {
            "day": "qdr:d",
            "week": "qdr:w",
            "month": "qdr:m",
            "year": "qdr:y" 
        }
        tbs_param = tbs_map.get(freshness, "qdr:m") # Default to past month if invalid

        full_query = f'{query} {location}'.strip()
        target_query = f'{full_query} ({" OR ".join(self.ats_domains)})'
        
        # update params for this run
        self.search.params["tbs"] = tbs_param

        # Rich console output
        console.scout_header()
        self.logger.info(f"🔎 ScoutAgent: Searching for '{full_query}' ({freshness} fresh) [Attempt {attempt}]...")
        
        try:
            # Synchronous call to SerpAPI (wrapped if needed, but simple enough here)
            raw_results = self.search.results(target_query)
            organic_results = raw_results.get('organic_results', [])
            
            if not organic_results:
                self.logger.warning("Search returned no results.")
                if attempt < 2:
                    return await self._reflect_and_retry(query, location, freshness, attempt, webhook_url)
                
                console.scout_results(query, location, [])
                return []
            
            valid_urls = self._filter_results(organic_results)
            
            if not valid_urls and attempt < 2:
                 self.logger.warning("No VALID ATS links found. Retrying...")
                 return await self._reflect_and_retry(query, location, freshness, attempt, webhook_url)
            
            # Convert valid_urls to ScrapedJob objects
            jobs = [
                ScrapedJob(
                    url=link, 
                    source_domain=next((domain for domain in self.valid_domains if domain in link), "unknown"),
                    query_matched=full_query
                )
                for link in valid_urls
            ]
            
            # Display rich formatted results
            console.scout_results(query, location, valid_urls)
            
            # Webhook Integration
            if webhook_url and jobs:
                try:
                    payload = {"query": full_query, "jobs": [j.model_dump() for j in jobs]}
                    def send_webhook():
                        response = requests.post(webhook_url, json=payload, timeout=5)
                        response.raise_for_status()
                    await asyncio.to_thread(send_webhook)
                    self.logger.info(f"✅ Webhook sent successfully to {webhook_url}")
                except Exception as e:
                    self.logger.error(f"Failed to send webhook: {e}")
            
            return jobs
            
        except Exception as e:
            self.logger.error(f"ScoutAgent Error: {str(e)}")
            console.error(f"Search failed: {str(e)}")
            return []

    async def _reflect_and_retry(self, query: str, location: str, freshness: str, attempt: int, webhook_url: Optional[str] = None) -> List[ScrapedJob]:
        """
        Self-Correction: Analyze why the search failed and generate a better query.
        """
        console.warning(f"🤔 ScoutAgent: 0 results found. Reflecting on strategy...")
        
        prompt = f"""
        You are a Google Search Expert for Recruitment.
        The user searched for: '{query} {location}' (Time filter: {freshness})
        
        Result: 0 valid job listings found on ATS (Greenhouse/Lever/Ashby).
        
        Reasoning: The query might be too specific (long tail keywords), have typos, or conflict with location filters.
        
        Task: Generate a BROADER, more likely to succeed search query.
        - Remove specific seniority levels if they are niche (e.g. "Senior Staff Principal" -> "Senior")
        - Remove conflicting terms.
        - Keep the essential skill/role.
        
        OUTPUT ONLY THE RAW QUERY STRING. NO EXPLANATION.
        """
        
        try:
            messages = [
                SystemMessage(content="You are a search query optimizer. Output ONLY the query string."),
                HumanMessage(content=prompt)
            ]
            response = self.llm.invoke(messages)
            new_query = response.content.strip().replace('"', '')
            
            console.info(f"💡 ScoutAgent Idea: Retrying with '{new_query}'")
            
            # Recursive retry with new query
            return await self.run(new_query, "", freshness, attempt + 1, webhook_url)
            
        except Exception as e:
            self.logger.error(f"Reflection Failed: {e}")
            return []

    def _filter_results(self, results: List[dict]) -> List[str]:
        valid_links = []
        seen: Set[str] = set()
        
        for r in results:
            link = r.get('link', '').strip()
            if not link or link in seen:
                continue
                
            if any(domain in link for domain in self.valid_domains):
                valid_links.append(link)
                seen.add(link)
                
        self.logger.info(f"✅ ScoutAgent: Found {len(valid_links)} valid jobs.")
        return valid_links
