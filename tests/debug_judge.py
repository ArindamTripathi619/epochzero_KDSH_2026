
import os
import pathway as pw
import pandas as pd
from src.models.llm_judge import ConsistencyJudge

def debug_judge():
    # Setup test table using pandas
    df = pd.DataFrame([{"prompt": "Hi", "query_id": 123}])
    t = pw.debug.table_from_pandas(df)
    
    judge = ConsistencyJudge(use_cloud=False) # Local for fast test
    
    try:
        final_results = judge.judge(t)
        print("Judge Result Columns:", final_results.column_names())
        try:
            print("Accessing query_id:", final_results.select(pw.this.query_id).column_names())
        except Exception as e:
            print(f"Cannot access query_id: {e}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_judge()
