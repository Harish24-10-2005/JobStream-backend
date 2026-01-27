
import os
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.pdf_service import pdf_service

data = {
    "company": "CyberDyne Systems",
    "company_info": {
        "industry": "Artificial Intelligence / Defense",
        "size": "Enterprise",
        "employee_count": "50,000+",
        "founded": "1997",
        "headquarters": "Sunnyvale, CA",
        "mission": "To create a safer future through advanced robotics.",
        "questions_to_ask": [
            "How do you handle ethical constraints in AI?",
            "What is the roadmap for Skynet v2?"
        ]
    },
    "culture_analysis": {
        "culture_type": "High Performance / Secretive",
        "work_life_balance": {
            "rating": "Demanding",
            "notes": "Expect long hours near launch deadlines."
        },
        "pros": ["Cutting edge tech", "High pay"],
        "cons": ["Possibility of judgment day", "Strict NDA"]
    },
    "red_flags": {
        "recommendation": "High Risk - Proceed with Caution",
        "overall_risk_level": "high",
        "company_red_flags": [
            {
               "flag": "Unsupervised AI development", 
               "severity": "high", 
               "how_to_verify": "Ask about kill-switches"
            }
        ]
    },
    "interview_insights": {
        "tips_from_candidates": [
            "Know your neural net theory.",
            "Don't mention John Connor."
        ]
    }
}

def test_pdf():
    print("Testing PDF Generation...")
    output_file = "Test_Dossier.pdf"
    path = pdf_service.generate_company_dossier(data, output_file)
    
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"✅ PDF Created: {path}")
        print(f"📄 Size: {size} bytes")
        
        if size > 1000:
            print("Size looks reasonable.")
        else:
            print("⚠️ Warning: File size is suspiciously small.")
    else:
        print("❌ Failed to create PDF.")

if __name__ == "__main__":
    test_pdf()
