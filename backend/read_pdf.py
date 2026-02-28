import pypdf

reader = pypdf.PdfReader(r"C:\Users\marti\.gemini\antigravity\scratch\trading-ai\Strategije in matematika v trgovanju.pdf")
text = ""
for page in reader.pages:
    text += page.extract_text() + "\n"

with open(r"C:\Users\marti\.gemini\antigravity\scratch\trading-ai\Strategije.txt", "w", encoding="utf-8") as f:
    f.write(text)

print("PDF extracted successfully.")
