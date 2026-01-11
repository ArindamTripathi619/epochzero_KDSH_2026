import os
import subprocess
import pandas as pd
import json
import time

def run_experiment(name, flags):
    print(f"\n>>> Running Experiment: {name}")
    print(f"Flags: {flags}")
    
    # 1. Clear previous results
    if os.path.exists("results.csv"):
        os.remove("results.csv")
    
    # 2. Run the pipeline with dedicated log
    log_file = f"log_{name.replace(' ', '_').lower()}.txt"
    env = os.environ.copy()
    env["INPUT_DATA"] = "Dataset/ablation_subset.csv"
    env["USE_CLOUD"] = "True"
    
    cmd = ["python", "main.py"] + flags
    try:
        with open(log_file, "w") as f:
            subprocess.run(cmd, env=env, stdout=f, stderr=f, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Experiment {name} failed: {e}")
        return False

    # 3. Wait/Check for results
    for _ in range(15): # Wait up to 15s for file write to stabilize
        if os.path.exists("results.csv") and os.path.getsize("results.csv") > 0:
            return True
        time.sleep(1)
    
    print(f"Warning: Results file not found for {name}")
    return False

def calculate_accuracy_robustly():
    try:
        train_df = pd.read_csv('Dataset/ablation_subset.csv')
        train_df['label_num'] = train_df['label'].map({'consistent': 1, 'contradict': 0})
        
        # Load predictions and handle potential debris
        if not os.path.exists('results.csv'):
             return 0, 0, 0
             
        pred_df = pd.read_csv('results.csv')
        
        # Merge on string IDs to be safe
        train_df['id_str'] = train_df['id'].astype(str)
        pred_df['Story_ID_str'] = pred_df['Story ID'].astype(str)
        
        results = pd.merge(train_df, pred_df, left_on='id_str', right_on='Story_ID_str')
        
        # Ensure Prediction is numeric
        results['Prediction'] = pd.to_numeric(results['Prediction'], errors='coerce').fillna(1).astype(int)
        
        correct = (results['label_num'] == results['Prediction']).sum()
        total = len(results)
        accuracy = (correct / total) * 100 if total > 0 else 0
        return accuracy, correct, total
    except Exception as e:
        print(f"Accuracy calculation error: {e}")
        return 0, 0, 0

def main():
    experiments = [
        ("Baseline", []),
        ("Expansion", ["--use-expansion"]),
        ("Reranking", ["--use-rerank"]),
        ("Dual Pass", ["--use-dual-pass"]),
        ("Expansion + Reranking", ["--use-expansion", "--use-rerank"]),
        ("Expansion + Dual Pass", ["--use-expansion", "--use-dual-pass"]),
        ("Reranking + Dual Pass", ["--use-rerank", "--use-dual-pass"]),
        ("Full Suite", ["--use-expansion", "--use-rerank", "--use-dual-pass"])
    ]
    
    summary = []
    for name, flags in experiments:
        success = run_experiment(name, flags)
        acc, corr, tot = calculate_accuracy_robustly()
        print(f"Result: {acc:.2f}% ({corr}/{tot})")
        summary.append({"name": name, "accuracy": float(acc), "correct": int(corr), "total": int(tot), "success": success})
            
    print("\n" + "="*40)
    print("FINAL ABLATION RESULTS")
    print("="*40)
    for r in summary:
        print(f"{r['name']}: {r['accuracy']:.2f}%")
    
    with open("ablation_results.json", "w") as f:
        json.dump(summary, f, indent=4)

if __name__ == "__main__":
    main()
