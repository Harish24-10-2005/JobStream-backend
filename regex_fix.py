import glob
import re

files = glob.glob('src/agents/*.py')
for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    def replacer(match):
        pre = match.group(1) 
        dict_content = match.group(2) 
        
        # If dict is empty {}
        if not dict_content.strip():
            pre = pre.rstrip(", ")
            return pre + ")"

        # Convert dictionary keys "key_name" to kwargs (key_name=)
        kwds = re.sub(r'[\'"]([a-zA-Z0-9_]+)[\'"]\s*:\s*', r'\1=', dict_content)
        return pre + kwds + ")"

    # Safely target slog.agent and slog.agent_error formats ending with {...}
    new_content = re.sub(r'(slog\.agent(?:_error)?\([^\{]+?,\s*)\{([^}]*)\}\)', replacer, content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {filepath}")
