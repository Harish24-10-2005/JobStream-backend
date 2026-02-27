import os

filepath = 'src/agents/company_agent.py'
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('{"company": company}', 'company=company')
text = text.replace('{"company": company, "error": str(e)}', 'company=company, error=str(e)')
text = text.replace('{"query": search_query, "error": str(e)}', 'query=search_query, error=str(e)')
text = text.replace('{"reason": check.blocked_reason}', 'reason=check.blocked_reason')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)
