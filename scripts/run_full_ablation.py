import os
import subprocess
import pandas as pd
import json
import time

def run_experiment(name, flags):
    print(f"\n{'='*70}")
    print(f">>> Running Experiment: {name}")
    print(f"Flags: {flags}")
    print(f"{'='*70}\n")
    
    # Clear previous results
    if os.path.exists("results.csv"):
        os.remove("results.csv")
    
    # Run the pipeline with dedicated log
    log_file = f"log_full_{name.replace(' ', '_').lower()}.txt"
    env = os.environ.copy()
    env["INPUT_DATA"] = "Dataset/train.csv"  # Full 80-row dataset
    env["USE_CLOUD"] = "True"
    
    cmd = ["python", "main.py"] + flags
    try:
        print(f"Executing: {' '.join(cmd)}")
        with open(log_file, "w") as f:
            subprocess.run(cmd, env=env, stdout=f, stderr=f, check=True, timeout=900)  # 15 min timeout
        print(f"✅ Experiment completed successfully")
        return True
    except subprocess.TimeoutExpired:
        print(f"⏱️ Experiment timed out after 15 minutes")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Experiment failed: {e}")
        return False

def calculate_accuracy():
    try:
        train_df = pd.read_csv('Dataset/train.csv')
        train_df['label_num'] = train_df['label'].map({'consistent': 1, 'contradict': 0})
        
        if not os.path.exists('results.csv'):
            return 0, 0, 0
             
        pred_df = pd.read_csv('results.csv')
        
        train_df['id_str'] = train_df['id'].astype(str)
        pred_df['Story_ID_str'] = pred_df['Story ID'].astype(str)
        
        results = pd.merge(train_df, pred_df, left_on='id_str', right_on='Story_ID_str')
        results['Prediction'] = pd.to_numeric(results['Prediction'], errors='coerce').fillna(1).astype(int)
        
        correct = (results['label_num'] == results['Prediction']).sum()
        total = len(results)
        accuracy = (correct / total) * 100 if total > 0 else 0
        return float(accuracy), int(correct), int(total)
    except Exception as e:
        print(f"⚠️ Accuracy calculation error: {e}")
        return 0, 0, 0

def main():
    print("="*70)
    print("FULL 80-ROW FEATURE EVALUATION")
    print("="*70)
    print()
    
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
        
        if success:
            # Wait for file to stabilize
            time.sleep(2)
            acc, corr, tot = calculate_accuracy()
            print(f"\n📊 Result: {acc:.2f}% ({corr}/{tot})")
        else:
            acc, corr, tot = 0, 0, 0
            print(f"\n❌ Experiment failed - no accuracy")
        
        summary.append({
            "name": name,
            "accuracy": float(acc),
            "correct": int(corr),
            "total": int(tot),
            "success": success
        })
        print()
    
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"{'Configuration':<30} {'Accuracy':<15} {'Correct/Total'}")
    print("-"*70)
    
    # Sort by accuracy descending
    summary_sorted = sorted(summary, key=lambda x: x['accuracy'], reverse=True)
    
    for r in summary_sorted:
        status = "✅" if r['success'] else "❌"
        print(f"{status} {r['name']:<28} {r['accuracy']:>6.2f}%        {r['correct']}/{r['total']}")
    
    print("="*70)
    
    # Save results
    with open("full_ablation_results.json", "w") as f:
        json.dump(summary_sorted, f, indent=4)
    
    print(f"\n✅ Results saved to full_ablation_results.json")
    
    # Find best configuration
    best = summary_sorted[0]
    if best['accuracy'] > 0:
        print(f"\n🎯 BEST CONFIGURATION: {best['name']}")
        print(f"   Accuracy: {best['accuracy']:.2f}%")
        print(f"   Improvement over baseline: {best['accuracy'] - summary[0]['accuracy']:.2f}%")

if __name__ == "__main__":
    main()
