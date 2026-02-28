import re

with open(r"C:\Users\marti\.gemini\antigravity\scratch\trading-ai\Strategije.txt", "r", encoding="utf-8") as f:
    text = f.read()

# completely remove newlines and replace with spaces
text = text.replace('\n', ' ')
# single space instead of multiple
text = re.sub(r'\s+', ' ', text)

import textwrap
wrapped_text = textwrap.fill(text, width=120)

with open(r"C:\Users\marti\.gemini\antigravity\scratch\trading-ai\dense.txt", "w", encoding="utf-8") as f:
    f.write(wrapped_text)

print("Dense text generated.")
