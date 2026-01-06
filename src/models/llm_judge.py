
import os
import json
import pathway as pw
from pathway.xpacks.llm import llms
from typing import Optional

class ConsistencyJudge:
    def __init__(self, use_cloud: bool = False, model_name: str = None):
        self.use_cloud = use_cloud
        
        if use_cloud:
            if not os.environ.get("OPENAI_API_KEY"):
                print("Warning: OPENAI_API_KEY not found. Defaulting to local model.")
                self.use_cloud = False
            else:
                self.model = llms.OpenAIChat(
                    model=model_name or "gpt-4o-mini",
                    api_key=os.environ["OPENAI_API_KEY"]
                )
        
        if not self.use_cloud:
            # Using LiteLLM provider for Ollama if available, 
            # or custom pathway LiteLLMChat (if configured)
            # In simpler cases, we can use a custom UDF to call Ollama API directly.
            # Let's assume LiteLLM is the bridge.
            self.model = llms.LiteLLMChat(
                model=model_name or "ollama/mistral",
                api_base="http://localhost:11434"
            )

    @pw.udf
    def build_consistency_prompt(self, backstory: str, character: str, evidence: str) -> str:
        return f"""
You are a literary consistency judge. Your task is to determine if a character's hypothesized backstory is globally consistent with the events of a novel.

Character: {character}
Hypothesized Backstory: {backstory}

Evidence from the novel:
{evidence}

Task:
1. Carefully compare the backstory with the provided evidence.
2. Determine if the backstory is "Consistent" (1) or "Contradicted" (0) by the evidence.
3. Provide a concise 1-2 line rationale.

Output format (JSON):
{{
  "label": 1 or 0,
  "rationale": "Your explanation here"
}}
"""

    def judge(self, prompts_table: pw.Table):
        """Applies the LLM model to the prompts."""
        return prompts_table.select(
            result=self.model(
                llms.prompt_chat_single_qa(pw.this.prompt)
            )
        )

if __name__ == "__main__":
    print("ConsistencyJudge module ready.")
