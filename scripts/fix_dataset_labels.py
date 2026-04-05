import pandas as pd
import requests
import json
import os
import time
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

API_BASE = "http://localhost:8000/v1"
DUMMY_KEY = "sk-dummy"
MODEL = "groq-llama-small"

def extract_character_name(backstory: str) -> str:
    prompt = f"""Extract the name of the main character precisely described in the following backstory.
Respond ONLY with the character's full name, nothing else. No punctuation, no conversational filler.

Backstory: {backstory}
Name:"""
    
    try:
        response = requests.post(
            f"{API_BASE}/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {DUMMY_KEY}"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0
            },
            timeout=10
        )
        if response.status_code == 200:
            name = response.json()["choices"][0]["message"]["content"].strip()
            # Clean up if the model returned something weird
            if len(name.split()) > 4 or len(name) > 30:
                return ""
            return name
    except Exception as e:
        print(f"Error on request: {e}")
    return ""

def fix_dataset(input_csv, output_csv):
    df = pd.read_csv(input_csv)
    print(f"Loaded {len(df)} records from {input_csv}.")
    
    corrected_names = []
    
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        new_name = extract_character_name(row["content"])
        if new_name and new_name.lower() != "unknown":
            corrected_names.append(new_name)
        else:
            corrected_names.append(row["char"]) # Fallback to original
        time.sleep(0.01)
        
    df["char"] = corrected_names
    df.to_csv(output_csv, index=False)
    print(f"Fixed dataset saved to {output_csv}")

if __name__ == "__main__":
    fix_dataset("Dataset/train.csv", "Dataset/train_fixed.csv")
