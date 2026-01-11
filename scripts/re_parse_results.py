import pandas as pd
import re
import os

def robust_parse(rationale):
    if pd.isna(rationale):
        return 1 # Default to consistent (Standard: 1)
    
    rat = str(rationale).lower()
    
    # Priority 1: Explicit Result markers
    if 'result: consistent' in rat or 'result": "consistent"' in rat:
        return 1
    if 'result: contradictory' in rat or 'result": "contradictory"' in rat:
        return 0
    
    # Priority 2: Label markers
    if '"label": 1' in rat or 'prediction": 1' in rat: return 1 # Consistent
    if '"label": 0' in rat or 'prediction": 0' in rat: return 0 # Contradictory

    # Priority 3: Textual affirmations
    if "is consistent" in rat or "decision to label as consistent" in rat:
        if "not" not in rat.split("consistent")[0][-10:]: # Look-behind for "not"
            return 1
    
    if "is contradictory" in rat or "decision to label as contradictory" in rat:
        if "not" not in rat.split("contradictory")[0][-10:]:
            return 0

    # Heuristic for the "Defense Attorney" overturn
    if "overturn the 'contradict'" in rat or "revised to reflect 'consistent'" in rat:
        return 1

    # Final fallback: Look for keywords but avoid negated ones
    has_contra = "contradict" in rat or "mismatch" in rat or "violation" in rat
    has_cons = "consistent" in rat or "silence" in rat or "no evidence of contradiction" in rat
    
    # If it talks about silence or no contradiction, it is consistent
    if "no contradiction" in rat or "novel is silent" in rat:
        return 1
        
    return 0 if has_contra else 1

def re_evaluate():
    input_file = 'results.csv'
    truth_file = 'Dataset/train.csv'
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found")
        return

    df = pd.read_csv(input_file)
    truth_df = pd.read_csv(truth_file)
    truth_map = dict(zip(truth_df['id'].astype(str), truth_df['label']))

    # Standardize column names
    if 'Story ID' in df.columns: df.rename(columns={'Story ID': 'id'}, inplace=True)
    
    correct = 0
    total = 0
    
    print(f"{'ID':<6} {'Truth':<12} {'New Pred':<10} {'Status'}")
    print("-" * 45)
    
    for i, row in df.iterrows():
        sid = str(row['id'])
        if sid not in truth_map: continue
        
        truth_str = truth_map[sid].lower()
        t_val = 1 if truth_str == 'consistent' else 0
        
        # Standard: 0=Contra, 1=Cons
        new_pred = robust_parse(row['Rationale'])
        
        is_correct = (new_pred == t_val)
        if is_correct: correct += 1
        total += 1
        
        status = "✅" if is_correct else "❌"
        t_disp = "Consistent" if t_val == 1 else "Contradict"
        n_disp = "Cons" if new_pred == 1 else "Contra"
        
        if i < 20 or not is_correct:
            print(f"{sid:<6} {t_disp:<12} {n_disp:<10} {status}")
        
        df.at[i, 'Prediction'] = new_pred

    acc = (correct / total) * 100
    print("-" * 45)
    print(f"Standardized Accuracy: {acc:.2f}% ({correct}/{total})")
    
    df.to_csv('results_final_standardized.csv', index=False)
    print("Saved final results to results_final_standardized.csv")

if __name__ == "__main__":
    re_evaluate()
