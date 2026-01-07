import os
import json
import pathway as pw
from typing import Optional
from pathway.xpacks.llm import llms
import threading
import time
import requests

# Global lock to ensure strictly sequential API calls if needed, 
# although local Ollama can handle some parallelism.
api_lock = threading.Lock()

@pw.udf
def build_consistency_prompt(backstory: str, character: str, evidence: str) -> str:
    return f"""
You are a senior literary editor and consistency judge. You have been given a character's Hypothetical Backstory and a set of Evidence Excerpts from the novel (context).

YOUR TASK:
Determine if the Backstory overlaps with, supports, or CONTRADICTS the established events in the novel.

INPUTS:
1. Character: {character}
2. Hypothetical Backstory: {backstory}
3. Evidence Excerpts (with temporal metadata):
{evidence}

ANALYSIS GUIDELINES:
- **Temporal Consistency**: If the backstory claims an event happened in "childhood", but Evidence from "Chapter 1" (adult life) contradicts the *result* of that event, mark it Inconsistent. Use the [Chapter/Progress] tags to establish a timeline.
- **Causal Consistency**: If the backstory claims a specific motivation (e.g., "hates water"), but Evidence shows them acting differently without explanation (e.g., "became a sailor"), it is a contradiction.
- **Silence != Contradiction**: If the novel never mentions the backstory events, and they fit plausibly, it is CONSISTENT. Only explicit contradictions matter.

OUTPUT FORMAT (JSON):
Return a JSON object with exactly two keys:
{{
  "label": 1 (Consistent) or 0 (Contradict),
  "rationale": "EVIDENCE: [Chapter X] Quote... -> CLAIM: Backstory says Y... -> ANALYSIS: This contradicts because..."
}}

The 'rationale' MUST be a specialized 'Dossier' string:
- Cite the specific EVIDENCE (Chapter/Progress) that drives your decision.
- Explicitly link it to a specific CLAIM in the backstory.
- Explain the logic briefly.
"""

class ConsistencyJudge:
    def __init__(self, use_cloud: bool = False, model_name: str = None):
        from dotenv import load_dotenv
        load_dotenv()
        
        self.use_cloud = use_cloud
        self.model_name = model_name or ("anthropic/claude-3.5-sonnet" if use_cloud else "mistral")
        
        if use_cloud:
            # OpenRouter is OpenAI-compatible
            self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
            self.base_url = "https://openrouter.ai/api/v1"
            if not self.api_key:
                print("Warning: No API key found for cloud. Defaulting to local model.")
                self.use_cloud = False
            else:
                self.model = llms.OpenAIChat(
                    model=self.model_name,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    max_tokens=500
                )
        
        if not self.use_cloud:
            # We will use direct requests to Ollama to avoid LiteLLMChat async bugs
            self.ollama_url = "http://localhost:11434/api/chat"

    def judge(self, prompts_table: pw.Table):
        """Applies the LLM model to the prompts with robust execution."""
        
        if self.use_cloud:
            @pw.udf
            def cloud_judge(prompt: str) -> str:
                from openai import OpenAI
                
                with api_lock:
                    print(f"DEBUG: Starting cloud call for query...")
                    client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                    
                    if "free" in self.model_name.lower():
                        time.sleep(12)
                    
                    try:
                        response = client.chat.completions.create(
                            model=self.model_name,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=500
                        )
                        content = response.choices[0].message.content
                        print(f"DEBUG: Successfully processed query with {self.model_name}")
                        return content
                    except Exception as e:
                        print(f"API Error for {self.model_name}: {e}")
                        return json.dumps({
                            "label": 0,
                            "rationale": f"API Error: {str(e)}"
                        })

            return prompts_table.select(
                *pw.this,
                result=cloud_judge(pw.this.prompt)
            )
        else:
            @pw.udf
            def local_judge(prompt: str) -> str:
                # Direct synchronous request to local Ollama
                payload = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "num_predict": 500
                    }
                }
                try:
                    print(f"DEBUG: Starting local Ollama call ({self.model_name})...")
                    # Increased timeout to 300s for complex reasoning
                    response = requests.post(self.ollama_url, json=payload, timeout=300)
                    response.raise_for_status()
                    result = response.json()
                    content = result['message']['content']
                    print(f"DEBUG: Successfully processed local query.")
                    return content
                except Exception as e:
                    print(f"Local Ollama Error: {e}")
                    return json.dumps({
                        "label": 0,
                        "rationale": f"Local LLM Error: {str(e)}"
                    })

            return prompts_table.select(
                *pw.this,
                result=local_judge(pw.this.prompt)
            )

if __name__ == "__main__":
    print("ConsistencyJudge module ready.")
