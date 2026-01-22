"""
Salary Negotiator Agent - AI-powered salary research and negotiation
Uses LangChain's DeepAgent for market research and negotiation strategies
"""
import json
import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq

from src.automators.base import BaseAgent
from src.models.job import JobAnalysis
from src.core.console import console
from src.core.config import settings


# ============================================
# Tool Definitions for Salary DeepAgent
# ============================================

def search_market_salary(
    role: str,
    location: str,
    experience_years: int = 3,
    company: str = ""
) -> Dict:
    """
    Search for market salary data for a given role and location.
    
    Args:
        role: Job title
        location: City/region
        experience_years: Years of experience
        company: Optional company name for specific data
    
    Returns:
        Salary range data with percentiles
    """
    console.step(1, 4, "Researching market salaries")
    
    # Use Groq LLM to estimate based on knowledge
    api_key = settings.groq_api_key_fallback.get_secret_value() if settings.groq_api_key_fallback else settings.groq_api_key.get_secret_value()
    
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.3,
        api_key=api_key
    )
    
    prompt = f"""
    Provide salary data for this role based on current market knowledge:
    
    Role: {role}
    Location: {location}
    Experience: {experience_years} years
    Company: {company or "General market"}
    
    Return ONLY valid JSON with realistic salary data in USD:
    {{
        "role": "{role}",
        "location": "{location}",
        "experience_years": {experience_years},
        "salary_range": {{
            "p25": 80000,
            "p50": 95000,
            "p75": 115000,
            "p90": 135000
        }},
        "total_compensation": {{
            "base_salary": 95000,
            "bonus_percentage": 10,
            "equity_range": "10000-50000"
        }},
        "factors_affecting_salary": [
            "factor 1",
            "factor 2"
        ],
        "market_trend": "growing|stable|declining",
        "demand_level": "high|medium|low",
        "data_sources": ["Levels.fyi", "Glassdoor", "LinkedIn Salary"],
        "notes": "Any relevant notes"
    }}
    """
    
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        
        result = llm.invoke([
            SystemMessage(content="You are a compensation analyst with access to current salary data. Be realistic and accurate. Output only valid JSON."),
            HumanMessage(content=prompt)
        ])
        
        content = result.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        
        parsed = json.loads(content)
        
        console.success(f"Market range: ${parsed['salary_range']['p25']:,} - ${parsed['salary_range']['p90']:,}")
        return parsed
        
    except Exception as e:
        console.error(f"Failed to get salary data: {e}")
        return {
            "error": str(e),
            "salary_range": {"p25": 0, "p50": 0, "p75": 0, "p90": 0}
        }


def analyze_offer(
    base_salary: int,
    bonus: int = 0,
    equity: int = 0,
    benefits: List[str] = None,
    role: str = "",
    location: str = ""
) -> Dict:
    """
    Analyze a job offer against market data.
    
    Args:
        base_salary: Offered base salary
        bonus: Annual bonus or sign-on
        equity: Stock/equity value
        benefits: List of benefits offered
        role: Job title for comparison
        location: Location for market comparison
    
    Returns:
        Analysis with rating and recommendations
    """
    console.step(2, 4, "Analyzing your offer")
    
    # Get market data for comparison
    market = search_market_salary(role, location) if role and location else {}
    market_range = market.get("salary_range", {})
    
    total_comp = base_salary + bonus + (equity // 4)  # Equity divided by 4-year vest
    
    # Determine percentile
    p25 = market_range.get("p25", base_salary * 0.85)
    p50 = market_range.get("p50", base_salary)
    p75 = market_range.get("p75", base_salary * 1.15)
    p90 = market_range.get("p90", base_salary * 1.30)
    
    if base_salary >= p90:
        percentile = "90th+"
        rating = "Excellent"
    elif base_salary >= p75:
        percentile = "75th-90th"
        rating = "Above Average"
    elif base_salary >= p50:
        percentile = "50th-75th"
        rating = "Average"
    elif base_salary >= p25:
        percentile = "25th-50th"
        rating = "Below Average"
    else:
        percentile = "Below 25th"
        rating = "Low"
    
    recommendations = []
    
    if base_salary < p50:
        recommendations.append(f"Consider negotiating base up to ${p50:,} (market median)")
    if not equity and role.lower().find("senior") >= 0:
        recommendations.append("Request equity/stock options for senior role")
    if not benefits or len(benefits) < 3:
        recommendations.append("Negotiate for additional benefits (401k match, WFH, PTO)")
    if bonus == 0:
        recommendations.append("Ask about annual bonus structure or sign-on bonus")
    
    analysis = {
        "offer_summary": {
            "base_salary": base_salary,
            "bonus": bonus,
            "equity": equity,
            "total_annual_comp": total_comp,
            "benefits": benefits or []
        },
        "market_comparison": {
            "percentile": percentile,
            "rating": rating,
            "market_median": p50,
            "market_75th": p75,
            "gap_to_median": p50 - base_salary if base_salary < p50 else 0
        },
        "recommendations": recommendations,
        "negotiation_priority": "base" if base_salary < p50 else "equity/benefits"
    }
    
    console.success(f"Offer rated: {rating} ({percentile} percentile)")
    return analysis


def generate_negotiation_script(
    current_offer: int,
    target_salary: int,
    role: str,
    reasoning: List[str] = None,
    tone: str = "professional"
) -> str:
    """
    Generate negotiation scripts and email templates.
    
    Args:
        current_offer: The offered salary
        target_salary: Your target salary
        role: The job role
        reasoning: Reasons to support your ask
        tone: professional, confident, or humble
    
    Returns:
        JSON string with negotiation scripts
    """
    console.step(3, 4, "Creating negotiation scripts")
    
    api_key = settings.groq_api_key_fallback.get_secret_value() if settings.groq_api_key_fallback else settings.groq_api_key.get_secret_value()
    
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.6,
        api_key=api_key
    )
    
    increase_pct = ((target_salary - current_offer) / current_offer) * 100
    reasons = ", ".join(reasoning) if reasoning else "market data, relevant experience"
    
    prompt = f"""
    Generate negotiation scripts for this salary negotiation:
    
    Current Offer: ${current_offer:,}
    Target Salary: ${target_salary:,}
    Increase Requested: {increase_pct:.1f}%
    Role: {role}
    Key Reasoning: {reasons}
    Tone: {tone}
    
    Create multiple options for different scenarios.
    
    Return ONLY valid JSON:
    {{
        "email_template": "Full email template...",
        "phone_script": {{
            "opening": "Thank you for the offer...",
            "ask": "Based on my research...",
            "justification": "My experience with...",
            "closing": "I'm excited about..."
        }},
        "counter_offer_phrases": [
            "phrase 1",
            "phrase 2"
        ],
        "if_they_say_no": {{
            "alternatives_to_ask": ["sign-on bonus", "extra PTO", "equity"],
            "response_script": "I understand budget constraints..."
        }},
        "red_flags_to_avoid": [
            "Don't...",
            "Never..."
        ],
        "power_phrases": [
            "I'm excited about the opportunity and want to find a number that works for both of us",
            "Based on my research and experience..."
        ]
    }}
    """
    
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        
        result = llm.invoke([
            SystemMessage(content="You are an expert salary negotiation coach. Create persuasive, professional scripts. Output only valid JSON."),
            HumanMessage(content=prompt)
        ])
        
        content = result.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        
        parsed = json.loads(content)
        console.success("Negotiation scripts created")
        return json.dumps(parsed)
        
    except Exception as e:
        console.error(f"Failed to generate scripts: {e}")
        return json.dumps({"error": str(e)})


def calculate_counter_offer(
    current_offer: int,
    market_data_json: str = "",
    your_experience_years: int = 3,
    competing_offers: List[int] = None
) -> Dict:
    """
    Calculate an optimal counter-offer based on market data and leverage.
    
    Args:
        current_offer: The offered salary
        market_data_json: JSON string of market data
        your_experience_years: Your years of experience
        competing_offers: List of other offers you have
    
    Returns:
        Counter-offer recommendation with justification
    """
    console.step(4, 4, "Calculating optimal counter-offer")
    
    try:
        market = json.loads(market_data_json) if market_data_json else {}
    except json.JSONDecodeError:
        market = {}
    
    market_range = market.get("salary_range", {})
    p50 = market_range.get("p50", current_offer * 1.05)
    p75 = market_range.get("p75", current_offer * 1.15)
    p90 = market_range.get("p90", current_offer * 1.25)
    
    # Calculate based on leverage
    leverage_score = 0
    
    if competing_offers:
        best_competing = max(competing_offers)
        leverage_score += 2
        if best_competing > current_offer:
            leverage_score += 1
    
    if your_experience_years >= 5:
        leverage_score += 1
    
    # Determine counter based on leverage
    if leverage_score >= 3:  # High leverage
        counter = min(p90, current_offer * 1.20)
        strategy = "aggressive"
    elif leverage_score >= 1:  # Medium leverage
        counter = min(p75, current_offer * 1.15)
        strategy = "moderate"
    else:  # Low leverage
        counter = min(p50 * 1.05, current_offer * 1.10)
        strategy = "conservative"
    
    # Round to nice number
    counter = round(counter / 1000) * 1000
    
    result = {
        "current_offer": current_offer,
        "recommended_counter": int(counter),
        "increase_amount": int(counter - current_offer),
        "increase_percentage": round(((counter - current_offer) / current_offer) * 100, 1),
        "strategy": strategy,
        "leverage_score": leverage_score,
        "justification": [],
        "walk_away_point": int(p50 * 0.95),
        "best_case_target": int(p75)
    }
    
    # Add justification
    if competing_offers and max(competing_offers) > current_offer:
        result["justification"].append(f"Have competing offer at ${max(competing_offers):,}")
    result["justification"].append(f"Market median for role: ${int(p50):,}")
    if your_experience_years >= 5:
        result["justification"].append(f"{your_experience_years} years of relevant experience")
    
    console.success(f"Recommended counter: ${int(counter):,} ({result['increase_percentage']}% increase)")
    return result


# ============================================
# Salary Agent System Prompt
# ============================================

SALARY_AGENT_SYSTEM_PROMPT = """You are an expert salary negotiation coach helping candidates maximize their compensation.

## Your Capabilities

### `search_market_salary`
Research current market salary data for any role and location.

### `analyze_offer`
Analyze a job offer against market data and provide a rating.

### `generate_negotiation_script`
Create professional negotiation emails and phone scripts.

### `calculate_counter_offer`
Calculate the optimal counter-offer based on market data and leverage.

## Guidelines

- Always research market data before giving advice
- Be realistic but advocate for the candidate
- Consider total compensation (base + bonus + equity)
- Factor in location cost of living
- Never recommend accepting below market without good reason
- Provide specific numbers and percentages
- Include backup options if the counter is rejected
"""


class SalaryAgent(BaseAgent):
    """
    DeepAgent-based Salary Negotiation Agent.
    
    Researches market salaries and generates negotiation strategies.
    """
    
    def __init__(self):
        super().__init__()
        
        if settings.groq_api_key_fallback:
            api_key = settings.groq_api_key_fallback.get_secret_value()
        else:
            api_key = settings.groq_api_key.get_secret_value()
        
        os.environ["GROQ_API_KEY"] = api_key
        
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.4,
            api_key=api_key
        )
    
    async def run(self, *args, **kwargs) -> Dict:
        """Required abstract method."""
        role = kwargs.get('role', '')
        location = kwargs.get('location', '')
        current_offer = kwargs.get('current_offer', 0)
        
        if current_offer:
            return await self.negotiate_offer(role, location, current_offer)
        else:
            return await self.research_salary(role, location)
    
    async def research_salary(
        self,
        role: str,
        location: str,
        experience_years: int = 3
    ) -> Dict:
        """
        Research market salary without an offer.
        
        Args:
            role: Job title
            location: City/region
            experience_years: Years of experience
            
        Returns:
            Market salary data and recommendations
        """
        console.subheader("💰 Salary Research Agent")
        console.info(f"Researching salaries for {role} in {location}...")
        
        market_data = search_market_salary(role, location, experience_years)
        
        return {
            "success": True,
            "market_data": market_data,
            "recommendation": f"Target the 50th-75th percentile: ${market_data['salary_range']['p50']:,} - ${market_data['salary_range']['p75']:,}"
        }
    
    async def negotiate_offer(
        self,
        role: str,
        location: str,
        current_offer: int,
        bonus: int = 0,
        equity: int = 0,
        experience_years: int = 3,
        competing_offers: List[int] = None
    ) -> Dict:
        """
        Full negotiation support for a specific offer.
        
        Args:
            role: Job title
            location: Location
            current_offer: Offered base salary
            bonus: Offered bonus
            equity: Offered equity
            experience_years: Your experience
            competing_offers: Other offers you have
            
        Returns:
            Complete negotiation package
        """
        console.subheader("💰 Salary Negotiation Agent")
        console.info("Analyzing offer and creating negotiation strategy...")
        
        # Step 1: Get market data
        market_data = search_market_salary(role, location, experience_years)
        
        # Step 2: Analyze the offer
        offer_analysis = analyze_offer(
            current_offer, bonus, equity,
            role=role, location=location
        )
        
        # Step 3: Calculate counter
        counter = calculate_counter_offer(
            current_offer,
            json.dumps(market_data),
            experience_years,
            competing_offers
        )
        
        # Step 4: Generate scripts
        scripts = generate_negotiation_script(
            current_offer,
            counter["recommended_counter"],
            role,
            counter["justification"]
        )
        
        return {
            "success": True,
            "market_data": market_data,
            "offer_analysis": offer_analysis,
            "counter_offer": counter,
            "negotiation_scripts": json.loads(scripts) if isinstance(scripts, str) else scripts
        }
    
    async def quick_counter(
        self,
        current_offer: int,
        role: str = "",
        location: str = ""
    ) -> Dict:
        """Quick counter-offer calculation."""
        console.subheader("💰 Quick Counter Calculation")
        
        market_json = ""
        if role and location:
            market = search_market_salary(role, location)
            market_json = json.dumps(market)
        
        counter = calculate_counter_offer(current_offer, market_json)
        
        return {
            "current_offer": current_offer,
            "recommended_counter": counter["recommended_counter"],
            "increase": f"${counter['increase_amount']:,} ({counter['increase_percentage']}%)",
            "strategy": counter["strategy"]
        }


# Lazy singleton instance
_salary_agent = None

def get_salary_agent() -> SalaryAgent:
    """Get or create the SalaryAgent singleton."""
    global _salary_agent
    if _salary_agent is None:
        _salary_agent = SalaryAgent()
    return _salary_agent

# For backwards compatibility
salary_agent = None  # Use get_salary_agent() instead
