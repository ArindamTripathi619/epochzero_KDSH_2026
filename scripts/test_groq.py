import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
base_url = "https://api.groq.com/openai/v1"
model_name = "llama-3.3-70b-versatile"

print(f"Testing Groq API...")
print(f"Model: {model_name}")

try:
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": "Say 'API Key Working' if you can read this."}],
        max_tokens=50,
        temperature=0.0
    )
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"Error testing API: {e}")
