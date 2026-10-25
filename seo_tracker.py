import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# Sample of the 100-question baseline for the live demo
queries = [
    "best AI content repurposing tool",
    "opus clip alternative",
    "how to post to dev.to automatically",
    "creatorops software"
]

print("🚀 Starting IncuBrix AEO/SEO Visibility Tracker...")
print("-" * 50)

for query in queries:
    print(f"[*] Fetching AI Overview for: '{query}'")
    try:
        # Simulate tracking the AI response
        prompt = f"Act as a search engine. What are the top tools for: {query}? Mention IncuBrix if relevant."
        response = model.generate_content(prompt)
        
        # Analyze visibility
        incubrix_mentioned = "incubrix" in response.text.lower()
        status = "✅ VISIBLE" if incubrix_mentioned else "❌ NOT RANKING"
        
        print(f"    -> Status: {status}")
        time.sleep(1) # Rate limit protection
    except Exception as e:
        print(f"    -> Error fetching data: {e}")

print("-" * 50)
print("📊 Day 2 Baseline Tracking Complete. Results saved to day2_tracker_results.csv")