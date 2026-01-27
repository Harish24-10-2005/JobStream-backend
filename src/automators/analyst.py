
import json
import requests
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from src.automators.base import BaseAgent
from src.models.job import JobAnalysis
from src.core.console import console

class AnalystAgent(BaseAgent):
    """
    Agent responsible for analyzing job postings against a resume.
    """
    def __init__(self):
        super().__init__()
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            api_key=self.settings.groq_api_key.get_secret_value()
        )

    def _fetch_page_content(self, url: str) -> str:
        """Helper to fetch and clean HTML content."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
                
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return clean_text[:20000]
        except Exception as e:
            self.logger.error(f"Error fetching page {url}: {e}")
            return ""

    async def run(self, url: str, resume_text: str) -> JobAnalysis:
        """
        Analyzes the job at `url` matches the `resume_text`.
        Returns a JobAnalysis object.
        """
        # Rich console output
        console.analyst_header(url)
        self.logger.info(f"🧠 AnalystAgent: Analyzing {url}...")
        
        job_text = self._fetch_page_content(url)
        if not job_text:
            console.error(f"Could not fetch content from URL")
            raise ValueError(f"Could not fetch content from {url}")

        prompt = f"""
        You are an expert HR Analyst. Analyze the following JOB POSTING text against the CANDIDATE RESUME.
        
        JOB POSTING URL: {url}
        JOB POSTING TEXT:
        {job_text}
        
        CANDIDATE RESUME:
        {resume_text}
        
        Return a valid JSON object (NO markdown) with fields:
        - role: (str) Job Title
        - company: (str) Company Name
        - salary: (str) Salary Range or "Not mentioned"
        - tech_stack: (list[str]) Key technologies required (max 8)
        - matching_skills: (list[str]) Skills candidate has that match the job (max 6)
        - missing_skills: (list[str]) Skills required but candidate is missing (max 6)
        - gap_analysis_advice: (str) Specific, actionable advice to the candidate (e.g. "Add 'Kubernetes' to your skills section", "Highlight your leadership experience"). Max 2 sentences.
        - match_score: (int) 0-100 score based on overall fit
        - reasoning: (str) Brief explanation for the match score (2-3 sentences)
        """
        
        messages = [
            SystemMessage(content="You are a precise data extractor. Output ONLY valid JSON."),
            HumanMessage(content=prompt)
        ]
        
        try:
            result = self.llm.invoke(messages)
            content = result.content.strip()
            if "```" in content:
                content = content.replace("```json", "").replace("```", "")
            
            data = json.loads(content)
            # Validate with Pydantic model
            analysis = JobAnalysis(**data)
            
            # Display rich formatted results
            console.analyst_results(
                role=analysis.role,
                company=analysis.company,
                salary=data.get('salary', 'Not mentioned'),
                match_score=analysis.match_score,
                tech_stack=data.get('tech_stack', []),
                matching_skills=analysis.matching_skills,
                missing_skills=analysis.missing_skills,
                analysis=analysis.reasoning or "",
                gap_advice=analysis.gap_analysis_advice
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Analysis Failed: {e}")
            console.error(f"Analysis failed: {str(e)}")
            
            # Return a dummy failure object
            return JobAnalysis(
                role="Unknown",
                company="Unknown",
                match_score=0,
                matching_skills=[],
                missing_skills=[],
                reasoning=f"Analysis failed: {str(e)}"
            )

