
import os
import pandas as pd
from dotenv import load_dotenv
from src.models.llm_judge import ConsistencyJudge
import pathway as pw
from pathway.xpacks.llm import llms

def test_openrouter():
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    print(f"OPENROUTER_API_KEY present: {api_key is not None}")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in .env")
        return

    judge = ConsistencyJudge(use_cloud=True)
    print(f"Judge use_cloud: {judge.use_cloud}")
    
    # Use pandas for table creation
    df = pd.DataFrame([{"prompt": "Is Paris the capital of France? Answer in one word."}])
    t = pw.debug.table_from_pandas(df)
    
    result = t.select(output=judge.model(llms.prompt_chat_single_qa(pw.this.prompt)))
    pw.debug.compute_and_print(result)

if __name__ == "__main__":
    test_openrouter()
