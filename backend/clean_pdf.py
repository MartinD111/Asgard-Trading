import re

with open(r"C:\Users\marti\.gemini\antigravity\scratch\trading-ai\Strategije.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Replace newlines with spaces, except when there are multiple newlines (paragraph breaks)
text = re.sub(r'([^\n])\n([^\n])', r'\1 \2', text)
text = re.sub(r'\n{2,}', '\n\n', text)
# Remove excessive spaces
text = re.sub(r' {2,}', ' ', text)

with open(r"C:\Users\marti\.gemini\antigravity\scratch\trading-ai\Strategije_clean.txt", "w", encoding="utf-8") as f:
    f.write(text)

print("PDF cleaned successfully.")
