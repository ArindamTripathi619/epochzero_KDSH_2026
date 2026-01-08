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
    def __init__(self, use_cloud: Optional[bool] = None, model_name: Optional[str] = None):
        from dotenv import load_dotenv
        load_dotenv()
        
        # Priority: Constructor Arg > Env Var > Default
        self.use_cloud = use_cloud if use_cloud is not None else (os.getenv("USE_CLOUD", "false").lower() == "true")
        self.model_name = model_name or os.getenv("LLM_MODEL")
        
        if self.use_cloud:
            self.openai_key = os.environ.get("OPENAI_API_KEY")
            self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
            self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")
            
            # Default model if none provided
            if not self.model_name:
                if self.openai_key:
                    self.model_name = "gpt-4o"
                elif self.anthropic_key:
                    self.model_name = "claude-3-5-sonnet-20240620"
                elif self.openrouter_key:
                    self.model_name = "anthropic/claude-3.5-sonnet"
                else:
                    self.model_name = "gpt-3.5-turbo" # Safe default
            
            # Determine Base URL and Key
            self.base_url = os.getenv("OPENAI_API_BASE")
            self.api_key = self.openai_key
            
            if self.openrouter_key and (not self.api_key or "openrouter" in self.model_name.lower()):
                self.api_key = self.openrouter_key
                self.base_url = self.base_url or "https://openrouter.ai/api/v1"
            
            if not self.api_key and not self.anthropic_key:
                print("Warning: No API key found for cloud. Defaulting to local model.")
                self.use_cloud = False
        
        if not self.use_cloud:
            self.model_name = self.model_name or "mistral"
            # We will use direct requests to Ollama to avoid LiteLLMChat async bugs
            self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

    def judge(self, prompts_table: pw.Table):
        """Applies the LLM model to the prompts with robust execution."""
        
        if self.use_cloud:
            @pw.udf
            def cloud_judge(prompt: str) -> str:
                # Local imports inside UDF for Pathway pickling
                from openai import OpenAI
                import anthropic
                
                with api_lock:
                    try:
                        # Anthropic Logic
                        if self.anthropic_key and ("claude" in self.model_name.lower() and "openrouter" not in (self.base_url or "")):
                            print(f"DEBUG: Starting Anthropic call ({self.model_name})...")
                            client = anthropic.Anthropic(api_key=self.anthropic_key)
                            message = client.messages.create(
                                model=self.model_name,
                                max_tokens=500,
                                messages=[{"role": "user", "content": prompt}]
                            )
                            # Anthropic returns list of content blocks
                            return message.content[0].text
                        
                        # OpenAI / OpenRouter Logic
                        print(f"DEBUG: Starting OpenAI-compatible call ({self.model_name})...")
                        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                        
                        # Handle OpenRouter free tier rate limits
                        if self.base_url and "openrouter" in self.base_url and "free" in self.model_name.lower():
                            time.sleep(1) # Reduced from 12s as OpenRouter free tier is better now
                        
                        response = client.chat.completions.create(
                            model=self.model_name,
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=500
                        )
                        return response.choices[0].message.content
                    except Exception as e:
                        print(f"Cloud API Error ({self.model_name}): {e}")
                        return json.dumps({
                            "label": 0,
                            "rationale": f"Cloud API Error: {str(e)}"
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
