
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.models.llm_judge import ConsistencyJudge

def test_judge():
    print("Initializing ConsistencyJudge...")
    # It now defaults to localhost:8000/v1 and sk-dummy
    judge = ConsistencyJudge()
    
    # Simple contradictory case
    prompt = """
    Identify if the following Backstory contradicts the Book Evidence.
    
    Backstory: The protagonist, John, was born in London and never left the city in his entire life.
    
    Book Evidence:
    - [Chapter 5] John looked out at the Tokyo skyline, remembering his childhood years spent in Japan before moving to London at age 20.
    
    VERDICT: CONTRADICTORY or VERDICT: CONSISTENT
    """
    
    print("Calling judge_single...")
    result = judge.judge_single(prompt)
    print(f"RESULT: {result}")
    
    if result['label'] == 0:
        print("SUCCESS: Contradiction detected!")
    else:
        print("FAILURE: Contradiction NOT detected. Is the LLM reachable?")

if __name__ == "__main__":
    test_judge()
