
import asyncio
import json
import os
import sys
from unittest.mock import patch

# Setup path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from src.automators.analyst import AnalystAgent
from src.core.config import settings

# ==========================================
# GOLDEN DATASET (Ground Truth)
# ==========================================

SAMPLE_JOB_TEXT = """
Senior Python Engineer at TechCorp.
We are looking for a backend engineer with 5+ years of experience.
Must have strong skills in Python, FastAPI, and Kubernetes.
Experience with AWS (Lambda, S3) is a plus.
Salary range: $150,000 - $180,000.
Remote (US Only).
"""

SAMPLE_RESUME = """
Jane Doe
Python Developer with 6 years experience.
Expert in Flask, Django, and FastAPI.
Proficient in Docker and Kubernetes.
"""

# ==========================================
# JUDGE EVALUATOR
# ==========================================

class LLMJudge:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            api_key=settings.groq_api_key.get_secret_value()
        )

    def evaluate_extraction(self, job_text: str, agent_output: dict) -> dict:
        """
        Asks the Judge LLM to grade the extraction quality.
        """
        prompt = f"""
        You are a QA Judge evaluating an AI Extraction Agent.
        
        SOURCE TEXT:
        {job_text}
        
        AGENT OUTPUT:
        {agent_output}
        
        TASK:
        Verify if the agent correctly extracted:
        1. Role ("Senior Python Engineer")
        2. Company ("TechCorp")
        3. Skills (Python, FastAPI, Kubernetes, AWS)
        4. Salary ("$150,000 - $180,000")
        
        Return JSON:
        {{
            "score": (int 1-5),
            "reasoning": (str),
            "pass": (bool)
        }}
        Score 5 if all critical info is present. Score 1 if hallucinates.
        """
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        print(f"\n🐛 RAW Judge Output: {content}")
        
        if "```" in content:
            # Extract content between first and last ``` 
            # Simple splitter approach
            parts = content.split("```")
            # Usually the json is in the second part if formatted like text ```json ... ``` text
            # If start is ```json, then parts[1] is content.
            for part in parts:
                if "{" in part and "}" in part:
                    content = part.strip()
                    if content.startswith("json"):
                         content = content[4:].strip()
                    break
        
        return json.loads(content)

async def main():
    print("🚀 Starting LLM Judge Verification...")
    
    # 1. Setup Agent with mocked network calls
    agent = AnalystAgent()
    
    # Mock the page fetcher to return our ground truth text
    with patch.object(agent, '_fetch_page_content', return_value=SAMPLE_JOB_TEXT):
        
        # 2. Run Agent
        print("🤖 running Analyst Agent...")
        result_obj = await agent.run("http://fake-url.com", SAMPLE_RESUME)
        
        # Convert Pydantic to dict for the Judge
        result_dict = {
            "role": result_obj.role,
            "company": result_obj.company,
            "tech_stack": result_obj.tech_stack,
            "salary": result_obj.salary or "Not found",
            "missing_skills": result_obj.missing_skills
        }
        
        print(f"\n📦 Agent Output:\n{json.dumps(result_dict, indent=2)}")
        
        # 3. Judge the Output
        print("\n👩‍⚖️ Asking LLM Judge for Verdict...")
        judge = LLMJudge()
        evaluation = judge.evaluate_extraction(SAMPLE_JOB_TEXT, result_dict)
        
        print(f"\n📝 Verdict:\n{json.dumps(evaluation, indent=2)}")
        
        # 4. Assert Quality Standards
        if evaluation["score"] >= 4 and evaluation["pass"]:
            print("\n✅ Verification PASSED")
            sys.exit(0)
        else:
            print(f"\n❌ Verification FAILED: {evaluation.get('reasoning')}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
