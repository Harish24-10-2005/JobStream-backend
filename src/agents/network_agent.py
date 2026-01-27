"""
NetworkAI Agent - LinkedIn X-Ray Search for Referral Intelligence

Uses SerpAPI (Google Search) to search publicly indexed LinkedIn profiles 
WITHOUT touching LinkedIn servers directly. This is safe - no risk of account bans.

The "X-Ray" technique searches: site:linkedin.com/in/ "College" "Company"
to find alumni, ex-colleagues, and location-based connections.
"""
import re
import asyncio
from typing import List, Optional
from langchain_community.utilities import SerpAPIWrapper
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from src.automators.base import BaseAgent
from src.models.profile import (
    UserProfile, 
    NetworkMatch, 
    NetworkSearchResult
)
from src.core.logger import logger


class NetworkAgent(BaseAgent):
    """
    Agent for finding networking contacts at target companies.
    
    Features:
    - X-Ray search via SerpAPI/Google (safe, no LinkedIn ban risk)
    - Alumni matching from user's education history
    - Location-based matching from user's city
    - Past employer matching for shared connections
    - AI-generated personalized outreach drafts
    """
    
    def __init__(self):
        super().__init__()
        self._llm = None
        self._search = None
        
    def _get_search(self) -> SerpAPIWrapper:
        """Lazy-load SerpAPI wrapper."""
        if not self._search:
            key = self.settings.serpapi_api_key.get_secret_value()
            if not key:
                raise ValueError("SERPAPI_API_KEY is required for NetworkAgent")
            
            self._search = SerpAPIWrapper(
                serpapi_api_key=key,
                params={
                    "engine": "google",
                    "google_domain": "google.com",
                    "gl": "us",
                    "hl": "en",
                    "num": 20
                }
            )
        return self._search
        
    def _get_llm(self):
        """Lazy-load LLM for outreach generation."""
        if not self._llm:
            self._llm = ChatGroq(
                model="llama-3.1-8b-instant",
                api_key=self.settings.groq_api_key.get_secret_value(),
                temperature=0.7,
            )
        return self._llm
    
    def _parse_linkedin_result(self, result: dict, connection_type: str, match_detail: str = None) -> Optional[NetworkMatch]:
        """
        Parse a SerpAPI search result into a NetworkMatch.
        
        Expected title format: "Harish R. - AI Engineer at Google | LinkedIn"
        """
        try:
            title = result.get("title", "")
            url = result.get("link", "")
            snippet = result.get("snippet", "")
            
            # Skip non-LinkedIn results
            if "linkedin.com/in/" not in url:
                return None
            
            # Remove " | LinkedIn" suffix
            title = re.sub(r'\s*\|\s*LinkedIn\s*$', '', title, flags=re.IGNORECASE)
            
            # Parse "Name - Headline" or "Name – Headline" (different dash chars)
            parts = re.split(r'\s*[-–—]\s*', title, maxsplit=1)
            
            name = parts[0].strip() if parts else "Unknown"
            headline = parts[1].strip() if len(parts) > 1 else snippet[:100] if snippet else ""
            
            # Skip if name looks invalid
            if len(name) < 2 or name.lower() in ["linkedin", "profile", "sign", "log in"]:
                return None
            
            match = NetworkMatch(
                name=name,
                headline=headline,
                profile_url=url,
                connection_type=connection_type,
                confidence_score=0.8 if headline else 0.5,
            )
            
            # Set specific match detail
            if connection_type == "alumni":
                match.college_match = match_detail
            elif connection_type == "location":
                match.location_match = match_detail
            elif connection_type == "company":
                match.company_match = match_detail
                
            return match
            
        except Exception as e:
            logger.debug(f"Failed to parse result: {e}")
            return None
    
    async def _xray_search(self, query: str, max_results: int = 15) -> List[dict]:
        """
        Perform X-Ray search via SerpAPI (Google Search).
        
        This searches Google's index of public LinkedIn profiles,
        NOT LinkedIn directly. Zero risk of account bans.
        """
        try:
            search = self._get_search()
            
            # Run sync SerpAPI call in thread pool to avoid blocking
            def _search():
                raw_results = search.results(query)
                return raw_results.get('organic_results', [])[:max_results]
            
            results = await asyncio.get_event_loop().run_in_executor(None, _search)
            logger.info(f"X-Ray search '{query[:50]}...' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"X-Ray search failed: {e}")
            return []
    
    async def _generate_outreach(self, match: NetworkMatch, user_profile: UserProfile, company: str) -> str:
        """Generate personalized outreach message using LLM."""
        try:
            llm = self._get_llm()
            
            user_name = user_profile.personal_information.first_name
            user_college = user_profile.education[0].university if user_profile.education else "my university"
            user_title = user_profile.experience[0].title if user_profile.experience else "Software Engineer"
            
            # Identify "Implicit Common Ground" (The "Warmth")
            common_ground = []
            if match.connection_type == "alumni":
                common_ground.append(f"We are both alumni of {match.college_match}. Go {match.college_match.split()[0]}!")
            elif match.connection_type == "location":
                 common_ground.append(f"I see we're neighbors in {match.location_match}.")
            elif match.connection_type == "company":
                 common_ground.append(f"We share history at {match.company_match}.")
            
            # Analyze Headlines for shared keywords (simple heuristic)
            user_skills = set()
            for skill_list in user_profile.skills.values():
                user_skills.update([s.lower() for s in skill_list])
            
            target_keywords = set(re.findall(r'\w+', match.headline.lower()))
            shared_tech = user_skills.intersection(target_keywords)
            
            if shared_tech:
                tech_str = ", ".join([t.title() for t in shared_tech])
                common_ground.append(f"I noticed your work with {tech_str} (which is my stack too).")
            
            warmth_context = " ".join(common_ground) if common_ground else "I admire your work at " + company

            prompt = f"""Write a "Warm Intro" LinkedIn connection request (max 300 chars).
Goal: Get them to accept.
Strategy: Use the specific "Common Ground" identified below to break the ice instantly.

SENDER: {user_name} ({user_title})
TARGET: {match.name} ({match.headline})
COMPANY: {company}

COMMON GROUND (Use this!):
{warmth_context}

RULES:
1. NO generic "I'd like to add you to my network".
2. Start DIRECTLY with the common ground (e.g., "Hi X, saw we're both Stanford alums...").
3. Be casual but professional.
4. End with a low-friction question or "Would love to connect."
5. MAX 300 CHARACTERS.

Write ONLY the message text.
"""

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            message = response.content.strip().replace('"', '')
            
            # fail-safe cleanup
            if len(message) > 300:
                message = message[:297] + "..."
                
            return message
            
        except Exception as e:
            logger.error(f"Failed to generate outreach: {e}")
            return f"Hi {match.name}, I see we have some shared background and I'd love to connect to follow your work at {company}."
    
    async def find_connections(
        self, 
        company: str, 
        user_profile: UserProfile,
        include_alumni: bool = True,
        include_location: bool = True,
        include_past_companies: bool = True,
        generate_outreach: bool = True,
        max_per_category: int = 5,
    ) -> NetworkSearchResult:
        """
        Find networking connections at a target company.
        
        Args:
            company: Target company name (e.g., "Google")
            user_profile: User's profile for matching criteria
            include_alumni: Search for college alumni at company
            include_location: Search for people from same city
            include_past_companies: Search for ex-colleagues
            generate_outreach: Generate AI outreach messages
            max_per_category: Max results per category
            
        Returns:
            NetworkSearchResult with categorized matches
        """
        result = NetworkSearchResult(
            company=company,
            search_query="",
            search_source="serpapi"
        )
        
        all_urls_seen = set()  # Deduplicate across categories
        
        # 1. Alumni Search
        if include_alumni and user_profile.education:
            for edu in user_profile.education[:2]:  # Max 2 schools
                college = edu.university
                query = f'site:linkedin.com/in/ "{college}" "{company}"'
                result.search_query = query  # Store last query
                
                search_results = await self._xray_search(query, max_results=max_per_category + 5)
                
                for r in search_results:
                    url = r.get("link", "")
                    if url in all_urls_seen:
                        continue
                        
                    match = self._parse_linkedin_result(r, "alumni", college)
                    if match:
                        all_urls_seen.add(url)
                        result.alumni_matches.append(match)
                        
                        if len(result.alumni_matches) >= max_per_category:
                            break
                
                # Rate limit between searches
                await asyncio.sleep(1.0)
        
        # 2. Location Search
        if include_location:
            city = user_profile.personal_information.location.city
            if city:
                query = f'site:linkedin.com/in/ "{city}" "{company}"'
                result.search_query = query
                
                search_results = await self._xray_search(query, max_results=max_per_category + 5)
                
                for r in search_results:
                    url = r.get("link", "")
                    if url in all_urls_seen:
                        continue
                        
                    match = self._parse_linkedin_result(r, "location", city)
                    if match:
                        all_urls_seen.add(url)
                        result.location_matches.append(match)
                        
                        if len(result.location_matches) >= max_per_category:
                            break
                
                await asyncio.sleep(1.0)
        
        # 3. Past Company Search (ex-colleagues)
        if include_past_companies and user_profile.experience:
            for exp in user_profile.experience[:2]:  # Max 2 past companies
                past_company = exp.company
                if past_company.lower() == company.lower():
                    continue  # Skip if same as target
                    
                query = f'site:linkedin.com/in/ "{past_company}" "{company}"'
                result.search_query = query
                
                search_results = await self._xray_search(query, max_results=max_per_category + 5)
                
                for r in search_results:
                    url = r.get("link", "")
                    if url in all_urls_seen:
                        continue
                        
                    match = self._parse_linkedin_result(r, "company", past_company)
                    if match:
                        all_urls_seen.add(url)
                        result.company_matches.append(match)
                        
                        if len(result.company_matches) >= max_per_category:
                            break
                
                await asyncio.sleep(1.0)
        
        # Calculate totals
        result.total_matches = (
            len(result.alumni_matches) + 
            len(result.location_matches) + 
            len(result.company_matches)
        )
        
        # Generate outreach messages for top matches
        if generate_outreach:
            # Prioritize: alumni > location > company
            top_matches = (
                result.alumni_matches[:3] + 
                result.location_matches[:2] + 
                result.company_matches[:2]
            )
            
            for match in top_matches:
                if not match.outreach_draft:
                    match.outreach_draft = await self._generate_outreach(
                        match, user_profile, company
                    )
                    await asyncio.sleep(0.5)  # Rate limit LLM calls
        
        logger.info(f"NetworkAI found {result.total_matches} connections at {company}")
        return result
    
    async def run(self, company: str, user_profile: UserProfile) -> NetworkSearchResult:
        """
        Main entry point - find connections at company.
        
        Args:
            company: Target company name
            user_profile: User's profile
            
        Returns:
            NetworkSearchResult with matches and outreach drafts
        """
        return await self.find_connections(company, user_profile)


# Global instance
network_agent = NetworkAgent()
