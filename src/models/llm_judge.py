import os
import json
import pathway as pw
from typing import Optional
import threading
import time
import requests
import re

# Global lock to ensure strictly sequential API calls if needed
api_lock = threading.Lock()

def build_consistency_prompt(backstory: str, character: str, evidence: str, programmatic_analysis: str = "") -> str:
    analysis_section = ""
    if programmatic_analysis:
        analysis_section = f"\n4. Programmatic Constraint Analysis:\n{programmatic_analysis}\n"

    return f"""You are a senior literary editor and consistency judge. You have been given a character's Hypothetical Backstory and a set of Evidence Excerpts from the novel (context).

YOUR TASK:
Determine if the Backstory CONTRADICTS the established events in the novel.

INPUTS:
1. Character: {character}
2. Hypothetical Backstory: {backstory}
3. Evidence Excerpts (with temporal metadata):
{evidence}
{analysis_section}

ANALYSIS GUIDELINES:
- **Temporal Consistency**: If the backstory claims an event at a specific time but Evidence shows different timing, it IS a contradiction.
- **Entity Collision**: If the backstory claims the character was in Place A, but Evidence shows they were in Place B at that time, it IS a contradiction.
- **Silence is NOT contradiction**: If the novel never mentions the backstory events, and they fit plausibly, it is CONSISTENT.
- **Core narrative divergence**: If the backstory's central claims directly conflict with established facts, it is CONTRADICTORY.

INSTRUCTIONS:
Think step by step. Analyze each claim in the backstory against the evidence excerpts. Quote specific evidence that supports or refutes each claim. Consider temporal, spatial, and causal consistency.

After your analysis, write your final verdict on a new line in EXACTLY this format:
VERDICT: CONSISTENT
or
VERDICT: CONTRADICTORY
"""

class ConsistencyJudge:
    def __init__(self, use_cloud: Optional[bool] = None, model_name: Optional[str] = None, use_dual_pass: bool = False):
        from dotenv import load_dotenv
        load_dotenv()
        
        self.use_cloud = use_cloud if use_cloud is not None else (os.getenv("USE_CLOUD", "false").lower() == "true")
        self.model_name = model_name or os.getenv("LLM_MODEL")
        self.use_dual_pass = use_dual_pass
        
        if self.use_cloud:
            self.openai_key = os.environ.get("OPENAI_API_KEY")
            self.api_key = self.openai_key
            self.base_url = os.getenv("OPENAI_API_BASE")
            if not self.model_name: self.model_name = "gpt-4o"
        
        if not self.use_cloud:
            self.model_name = self.model_name or "mistral"
            self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

    def _parse_verdict(self, text: str) -> dict:
        """Parse a free-form LLM response into a structured verdict."""
        if not text:
            return {"label": 1, "rationale": "Empty LLM response."}
        
        text_upper = text.upper()
        
        # Look for explicit VERDICT line
        verdict_match = re.search(r'VERDICT:\s*(CONSISTENT|CONTRADICTORY|CONTRADICT)', text_upper)
        if verdict_match:
            verdict = verdict_match.group(1)
            label = 0 if "CONTRADICT" in verdict else 1
            return {"label": label, "rationale": text.strip()[:500]}
        
        # Fallback: scan for strong indicators in the last 200 chars (conclusion area)
        conclusion = text_upper[-300:]
        
        contradict_signals = ["CONTRADICTS", "CONTRADICTORY", "INCONSISTENT", "IS A CONTRADICTION", 
                              "DIRECTLY CONFLICTS", "DOES CONTRADICT", "FUNDAMENTALLY CONFLICTS"]
        consistent_signals = ["CONSISTENT", "NO CONTRADICTION", "DOES NOT CONTRADICT",
                              "PLAUSIBLE", "COMPATIBLE", "NO DIRECT CONFLICT"]
        
        contra_score = sum(1 for s in contradict_signals if s in conclusion)
        consist_score = sum(1 for s in consistent_signals if s in conclusion)
        
        if contra_score > consist_score:
            label = 0
        elif consist_score > contra_score:
            label = 1
        else:
            # Ultimate fallback: default to consistent (conservative)
            label = 1
        
        return {"label": label, "rationale": text.strip()[:500]}

    def judge_single(self, prompt: str) -> dict:
        """Atomic judge call — lets LLM reason freely, then parses verdict."""
        if self.use_cloud:
            from openai import OpenAI
            try:
                client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                    # NO response_format — let the model think freely
                )
                res_text = response.choices[0].message.content
                return self._parse_verdict(res_text)
            except Exception as e:
                print(f"DEBUG: LLM single pass failed: {e}")
                return {"label": 1, "rationale": f"LLM Error: {str(e)}"}
        else:
            try:
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False
                    # NO format: "json" — let the model think freely
                }
                res = requests.post(self.ollama_url, json=payload, timeout=30)
                if res.status_code == 200:
                    return self._parse_verdict(res.json().get("response", ""))
            except: pass
            return {"label": 1, "rationale": "Local LLM unreachable."}

    def judge(self, prompts_table: pw.Table):
        if self.use_cloud:
            @pw.udf
            def cloud_judge(prompt: str) -> str:
                from openai import OpenAI
                try:
                    print(f"DEBUG: Cloud Judge calling {self.model_name}...", flush=True)
                    client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                    response = client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0
                    )
                    initial_judgment = response.choices[0].message.content
                    result = self._parse_verdict(initial_judgment)
                    return json.dumps(result)
                    
                except Exception as e:
                    return json.dumps({"label": 1, "rationale": f"Cloud Error: {str(e)}"})
            return prompts_table.select(result=cloud_judge(pw.this.prompt))
        else:
            @pw.udf
            def local_judge(prompt: str) -> str:
                try:
                    payload = {
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False
                    }
                    res = requests.post(self.ollama_url, json=payload, timeout=60)
                    if res.status_code == 200:
                        content = res.json().get("message", {}).get("content", "")
                        result = self._parse_verdict(content)
                        return json.dumps(result)
                except Exception as e:
                    return json.dumps({"label": 1, "rationale": f"Local Error: {str(e)}"})
                return json.dumps({"label": 1, "rationale": "Ollama unreachable."})
            return prompts_table.select(result=local_judge(pw.this.prompt))
