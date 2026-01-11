import os
import json
import pathway as pw
from typing import Optional
import threading
import time
import requests

# Global lock to ensure strictly sequential API calls if needed
api_lock = threading.Lock()

@pw.udf
def build_consistency_prompt(backstory: str, character: str, evidence: str, programmatic_analysis: str = "") -> str:
    analysis_section = ""
    if programmatic_analysis:
        analysis_section = f"\n4. Programmatic Constraint Analysis:\n{programmatic_analysis}\n"

    return f"""
You are a senior literary editor and consistency judge. You have been given a character's Hypothetical Backstory and a set of Evidence Excerpts from the novel (context).

YOUR TASK:
Determine if the Backstory overlaps with, supports, or CONTRADICTS the established events in the novel.

INPUTS:
1. Character: {character}
2. Hypothetical Backstory: {backstory}
3. Evidence Excerpts (with temporal metadata):
{evidence}
{analysis_section}

ANALYSIS GUIDELINES:
- **Temporal Consistency**: If the backstory claims an event happened in "childhood", but Evidence from "Chapter 1" (adult life) contradicts the *result* of that event, mark it Inconsistent. 
- **Silence != Contradiction**: If the novel never mentions the backstory events, and they fit plausibly, it is CONSISTENT. Only explicit contradictions matter.
- **DEFAULT TO CONSISTENT**: If the evidence is vague or silent, YOU MUST LABEL IT AS CONSISTENT (1). Proof of contradiction must be IRREFUTABLE.

OUTPUT FORMAT (JSON):
Return a JSON object with exactly two keys:
{{
  "label": 1 (Consistent) or 0 (Contradict),
  "rationale": "EVIDENCE: [Chapter X] Quote... -> CLAIM: Backstory says Y... -> ANALYSIS: This contradicts because..."
}}
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
                        response_format={"type": "json_object"},
                        temperature=0.0 
                    )
                    initial_judgment = response.choices[0].message.content
                    
                    if not self.use_dual_pass:
                        return initial_judgment
                    
                    print(f"DEBUG: Dual-Pass Review starting...", flush=True)
                    review_prompt = f"""
                    You are a Lead Editor reviewing a Consistency Judge's decision.
                    INITIAL DECISION: {initial_judgment}
                    
                    TASK: Act as 'Defense Attorney'. 
                    - If the judge found a contradiction (label: 0), verify if it is IRREFUTABLE. 
                    - If the evidence is SILENT or VAGUE, you MUST OVERTURN to Consistent (label: 1).
                    - If already Consistent, maintain it.
                    
                    Return the FINAL JSON in the same format: {{"label": 0/1, "rationale": "..."}}
                    """
                    response2 = client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "user", "content": prompt}, 
                            {"role": "assistant", "content": initial_judgment}, 
                            {"role": "user", "content": review_prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.0
                    )
                    return response2.choices[0].message.content
                except Exception as e:
                    print(f"Cloud Error: {e}", flush=True)
                    return json.dumps({"label": 1, "rationale": f"Fallback: {str(e)}"})

            return prompts_table.select(*pw.this, result=cloud_judge(pw.this.prompt))
        else:
            @pw.udf
            def local_judge(prompt: str) -> str:
                def call_ollama(p):
                    payload = {"model": self.model_name, "messages": [{"role": "user", "content": p}], "stream": False, "options": {"temperature": 0}}
                    resp = requests.post(self.ollama_url, json=payload, timeout=300)
                    return resp.json()['message']['content']
                try:
                    with api_lock: initial = call_ollama(prompt)
                    if not self.use_dual_pass: return initial
                    review_prompt = f"Lead Editor Review: {initial}. Ensure Label 1 if evidence is silent."
                    with api_lock: return call_ollama(review_prompt)
                except Exception as e:
                    return json.dumps({"label": 1, "rationale": f"Local Fallback: {str(e)}"})
            return prompts_table.select(*pw.this, result=local_judge(pw.this.prompt))
