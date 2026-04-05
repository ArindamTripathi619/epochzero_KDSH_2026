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

def _call_with_retry(client, model: str, messages: list, max_retries: int = 10) -> str:
    """Call LLM with exponential backoff retry logic for 429s and other transient errors."""
    for attempt in range(max_retries):
        try:
            # Respect rate limits with a small baseline delay
            # time.sleep(0.5) 
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=800
            )
            content = response.choices[0].message.content
            if content:
                return content
        except Exception as e:
            err_msg = str(e)
            # If rate limited (429), wait longer
            if "429" in err_msg or "rate_limit" in err_msg.lower():
                wait_time = (2 ** attempt) + 5 # More aggressive backoff
            else:
                wait_time = (2 ** attempt) + 1
            
            print(f"DEBUG: Attempt {attempt+1} failed for {model}: {err_msg}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            
    raise Exception(f"All {max_retries} attempts failed for model {model}")

def build_consistency_prompt(backstory: str, character: str, evidence: str, programmatic_analysis: str = "", plot_summary: str = "") -> str:
    analysis_section = ""
    if programmatic_analysis:
        analysis_section = f"\n4. Programmatic Constraint Analysis:\n{programmatic_analysis}\n"

    plot_section = ""
    if plot_summary:
        plot_section = f"5. Mini Plot-Map Summarization:\n{plot_summary}\n"

    return f"""You are a senior literary editor and consistency judge. You have been given a character's Hypothetical Backstory and a set of Evidence Excerpts from the novel (context).

YOUR TASK:
Determine if the Backstory CONTRADICTS the established events in the novel.

INPUTS:
1. Character: {character} (Note: metadata may be generic; focus on the provided backstory).
2. Hypothetical Backstory: {backstory}
3. Evidence Excerpts (with temporal metadata):
{evidence}
{analysis_section}
{plot_section}

ANALYSIS GUIDELINES:
- **Temporal Consistency**: If the backstory claims an event at a specific time but Evidence shows different timing, it IS a contradiction.
- **Entity Collision**: If the backstory claims the character was in Place A, but Evidence shows they were in Place B at that time, it IS a contradiction.
- **Silence is NOT contradiction**: If the novel never mentions the backstory events, and they fit plausibly, it is CONSISTENT.
- **Core narrative divergence**: If the backstory's central claims directly conflict with established facts, it is CONTRADICTORY.

INSTRUCTIONS:
Think step by step in explicitly numbered steps to force a comprehensive analysis:

Step 1 - Timeline Check: Do the dates/years in the backstory conflict with any evidence?
Step 2 - Location Check: Are proposed locations compatible?
Step 3 - Character State Check: Do described beliefs/traits match the novel's characterization?
Step 4 - Causal Check: Do backstory events make later novel events plausible or impossible?
Step 5 - Verdict: Given all above, write your final verdict on a new line in EXACTLY this format:
VERDICT: CONSISTENT
or
VERDICT: CONTRADICTORY
"""

class ConsistencyJudge:
    def __init__(self, use_cloud: Optional[bool] = None, model_name: Optional[str] = None, use_dual_pass: bool = False):
        from dotenv import load_dotenv
        load_dotenv()
        
        # We always want to use the OpenAI-style client for the LiteLLM rotator on port 8000
        self.use_cloud = True 
        self.model_name = model_name or os.getenv("LLM_MODEL") or "groq-llama"
        self.use_dual_pass = use_dual_pass
        
        self.api_key = os.environ.get("OPENAI_API_KEY") or "sk-dummy"
        self.base_url = os.getenv("OPENAI_API_BASE") or "http://localhost:8000/v1"

    def _parse_verdict(self, text: str) -> dict:
        """Parse a free-form LLM response into a structured verdict with scoring and evidence."""
        if not text:
            return {"label": 1, "rationale": "Empty LLM response.", "score": 0, "evidence": ""}
        
        text_upper = text.upper()
        
        # Look for explicit VERDICT line
        verdict_match = re.search(r'VERDICT:\s*(CONSISTENT|CONTRADICTORY|CONTRADICT|INCONSISTENT)', text_upper)
        label = 1 # Default
        if verdict_match:
            verdict = verdict_match.group(1)
            label = 0 if any(x in verdict for x in ["CONTRADICT", "INCONSISTENT"]) else 1
        
        # Look for SCORE (1-10)
        score = 5 # Default mid-point
        score_match = re.search(r'CONTRADICTION_SCORE:\s*(\d+)', text_upper)
        if score_match:
            try:
                score = int(score_match.group(1))
            except: pass

        # Look for DIRECT_QUOTE
        evidence = ""
        evidence_match = re.search(r'DIRECT_QUOTE:\s*(.*)', text, re.IGNORECASE)
        if evidence_match:
            evidence = evidence_match.group(1).strip()

        return {"label": label, "rationale": text.strip()[:600], "score": score, "evidence": evidence}

    def _call_model(self, model: str, prompt: str) -> dict:
        """Call a specific model via the LiteLLM rotator with automatic retries."""
        from openai import OpenAI
        try:
            # We use the lock to prevent overlapping calls that trigger 429s too easily
            # However, with 3 ensemble models, we might want some parallelism.
            # Let's use a smaller lock or just rely on the retry logic.
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            res_text = _call_with_retry(
                client, 
                model=model, 
                messages=[{"role": "user", "content": prompt}]
            )
            
            return self._parse_verdict(res_text)
        except Exception as e:
            print(f"DEBUG: FINAL FAILURE on model {model} after retries: {e}")
            # If it's a FINAL failure, we STILL return consistent to avoid crashing the pipeline,
            # but we mark it clearly in the rationale.
            return {"label": 1, "rationale": f"CRITICAL_FAILURE on {model}: {str(e)}", "score": 0, "evidence": ""}

    def judge_single(self, prompt: str) -> dict:
        """Atomic judge call — applies multi-model consensus and balanced devil's advocate."""
        # Space out stories to prevent LiteLLM saturation
        time.sleep(2.0)
        
        ensemble_models = ["groq-llama", "groq-qwen", "groq-kimi"]
        devils_advocate_model = "groq-gpt-oss" 
        
        results = []
        labels = []
        
        if self.model_name not in ensemble_models:
             ensemble_models[0] = self.model_name
             
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self._call_model, m, prompt): m for m in ensemble_models}
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                results.append(res)
                labels.append(res["label"])
        
        ensemble_rationale = " | ".join([f"M{i}: {r['rationale'][:100]}" for i, r in enumerate(results)])
        ensemble_sum = sum(labels)
        
        # Case A: Split Decision (2:1 or 1:2) -> Ask DA to arbitrate
        # Case B: Unanimous -> DA tries to find hidden flaws
        is_split = (ensemble_sum == 1 or ensemble_sum == 2)
        
        arbitration_instr = ""
        if is_split:
            arbitration_instr = f"\nThe ensemble is split. 1 model found a contradiction, 2 did not. Review these rationales:\n{ensemble_rationale}\nDecide which side is logically superior."

        devils_prompt = f"""### DEVIL'S ADVOCATE BALANCED LOGICAL STRESS TEST ###
Your purpose is to find if a contradiction TRULY exists. 
You must provide a CONTRADICTION_SCORE (1-10) where 1 is certainly consistent, 10 is blatant contradiction.
You MUST provide a DIRECT_QUOTE from the provided evidence excerpts to support any claim of contradiction.

{prompt}
{arbitration_instr}
"""
        # Intensive pass with high-capacity model
        da_res = self._call_model(devils_advocate_model, devils_prompt)
        
        # OVERRIDE LOGIC:
        # 1. If DA finds a contradiction (0) AND provides evidence (quote) AND score is >= 8, we override.
        # 2. If ensemble says 1 (Consist) but DA presents strong proof (score 8+), result = 0.
        # 3. If ensemble says 0 (Contradict) but DA score is <= 3, result = 1.
        
        final_label = 1 if ensemble_sum >= 2 else 0
        override_msg = ""
        
        if final_label == 1 and da_res["label"] == 0 and da_res["score"] >= 8 and len(da_res["evidence"]) > 10:
            final_label = 0
            override_msg = f"[DA OVERRIDE: Contradiction found with score {da_res['score']} and quote '{da_res['evidence'][:50]}']"
        elif final_label == 0 and da_res["score"] <= 3:
            final_label = 1
            override_msg = f"[DA OVERRIDE: Consistent - Dismissed weak contradiction (score {da_res['score']})]"

        return {
            "label": final_label, 
            "rationale": f"{override_msg} | DA_SCORE: {da_res['score']} | {ensemble_rationale} | DA_FINAL: {da_res['rationale'][:200]}",
            "confidence": "High" if da_res["score"] >= 8 or da_res["score"] <= 2 else "Medium"
        }

    def judge(self, prompts_table: pw.Table):
        @pw.udf
        def ensemble_judge(prompt: str) -> str:
            result = self.judge_single(prompt)
            return json.dumps(result)
        return prompts_table.select(result=ensemble_judge(pw.this.prompt))
