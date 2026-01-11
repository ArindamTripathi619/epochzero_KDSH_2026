import os
from openai import OpenAI
from dotenv import load_dotenv

def test_openai():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in .env")
        return

    print(f"Testing OpenAI API with key: {api_key[:8]}...{api_key[-4:]}")
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello, are you active?"}],
            max_tokens=10
        )
        print("Success! Response:", response.choices[0].message.content)
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    test_openai()
