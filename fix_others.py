import glob
import os

files = glob.glob('src/agents/*.py')
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    text = text.replace('{"job": job_analysis.role}', 'job=job_analysis.role')
    text = text.replace('{"job": job_analysis.role, "error": str(e)}', 'job=job_analysis.role, error=str(e)')
    
    # cover letter agent specific
    text = text.replace('{"job": job_analysis.role, "target": target_company}', 'job=job_analysis.role, target=target_company')
    text = text.replace('{"step": "research", "company": job_analysis.company}', 'step="research", company=job_analysis.company')
    text = text.replace('{"step": "research", "error": str(e)}', 'step="research", error=str(e)')
    text = text.replace('{"step": "drafting", "length": len(draft)}', 'step="drafting", length=len(draft)')
    text = text.replace('{"step": "drafting", "error": str(e)}', 'step="drafting", error=str(e)')
    text = text.replace('{"step": "refinement"}', 'step="refinement"')
    text = text.replace('{"step": "refinement", "error": str(e)}', 'step="refinement", error=str(e)')
    
    # interview agent specific
    text = text.replace('{"step": "behavioral_questions"}', 'step="behavioral_questions"')
    text = text.replace('{"step": "behavioral_questions", "error": str(e)}', 'step="behavioral_questions", error=str(e)')
    text = text.replace('{"step": "technical_questions"}', 'step="technical_questions"')
    text = text.replace('{"step": "technical_questions", "error": str(e)}', 'step="technical_questions", error=str(e)')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
