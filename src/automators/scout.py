
from typing import List, Set
from langchain_community.utilities import SerpAPIWrapper
from src.automators.base import BaseAgent
from src.core.console import console

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
        self.ats_domains = ["site:greenhouse.io", "site:lever.co", "site:ashbyhq.com"]
        self.valid_domains = ["greenhouse.io", "lever.co", "ashbyhq.com"]

    async def run(self, query: str, location: str = "") -> List[str]:
        """
        Searches for jobs targeting ATS domains.
        """
        full_query = f'{query} {location}'.strip()
        target_query = f'{full_query} ({" OR ".join(self.ats_domains)})'
        
        # Rich console output
        console.scout_header()
        self.logger.info(f"🔎 ScoutAgent: Searching for '{full_query}'...")
        
        try:
            # Synchronous call to SerpAPI (wrapped if needed, but simple enough here)
            raw_results = self.search.results(target_query)
            organic_results = raw_results.get('organic_results', [])
            
            if not organic_results:
                self.logger.warning("Search returned no results.")
                console.scout_results(query, location, [])
                return []
            
            valid_urls = self._filter_results(organic_results)
            
            # Display rich formatted results
            console.scout_results(query, location, valid_urls)
            
            return valid_urls
            
        except Exception as e:
            self.logger.error(f"ScoutAgent Error: {str(e)}")
            console.error(f"Search failed: {str(e)}")
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
