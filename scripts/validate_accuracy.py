import pandas as pd
import os

def calculate_accuracy():
    # 1. Load ground truth
    dataset_path = os.getenv("INPUT_DATA", "Dataset/train.csv")
    print(f"[DEBUG] Validation using dataset: {dataset_path}")
    train_df = pd.read_csv(dataset_path)
    
    # 2. Convert ground truth labels to numeric (consistent -> 1, contradict -> 0)
    train_df['label_num'] = train_df['label'].map({'consistent': 1, 'contradict': 0})
    
    # 3. Create a temporary results file for training data
    print("Running pipeline on training data for validation...")
    if os.path.exists("results.csv"):
         if os.path.isfile("results.csv"): os.remove("results.csv")
         else: import shutil; shutil.rmtree("results.csv")
         
    os.environ["INPUT_DATA"] = "Dataset/train_parts/"
    
    import subprocess
    import time
    
    p = subprocess.Popen(["/home/DevCrewX/Projects/epochzero_KDSH_2026/venv/bin/python3", "main.py"], 
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    # Wait for completion
    print("Waiting for NLI results...")
    max_wait = 600 # 10 mins
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if os.path.exists("results.csv"):
             try:
                  # Check if it is a directory or file
                  if os.path.isdir("results.csv"):
                       all_files = [f for f in os.listdir("results.csv") if f.endswith(".csv")]
                       count = sum([len(pd.read_csv(os.path.join("results.csv", f))) for f in all_files])
                  else:
                       with open("results.csv", "r") as f:
                            count = len(f.readlines()) - 1
                  
                  if count >= 80: # This condition is now secondary to the stdout check
                       print(f"Detected {count} results. Finishing...")
                       break
             except: pass
        
        if p.poll() is not None:
            # Check for error
            if p.returncode != 0:
                print(f"Pipeline failed with exit code: {p.returncode}")
                # Print last bits of output if possible
                break
            print("Pipeline process terminated early.")
            break
        time.sleep(10)
    
    p.terminate()
    try:
        p.wait(timeout=5)
    except:
        p.kill()
    
    # 4. Load our predictions
    if not os.path.exists("results.csv"):
        print("Error: results.csv was not generated!")
        return

    try:
        pred_df = pd.read_csv("results.csv")
    except Exception as e:
        print(f"Direct read failed, trying robust read: {e}")
        pred_df = pd.read_csv("results.csv", on_bad_lines='skip', engine='python')
    
    # 5. Merge and compare
    # Cast both to string to avoid int64 vs object merge errors and handle Pathway pointers if they persist
    train_df['id_str'] = train_df['id'].astype(str)
    
    # Ensure Prediction is numeric and Story ID is string for merge
    pred_df['Prediction'] = pd.to_numeric(pred_df['Prediction'], errors='coerce')
    pred_df['Story_ID_str'] = pred_df['Story ID'].astype(str)
    
    results = pd.merge(train_df, pred_df, left_on='id_str', right_on='Story_ID_str')
    
    if len(results) == 0:
        print("Error: No matches found between train.csv and results.csv! Check the IDs.")
        print(f"Sample Train IDs: {train_df['id_str'].head(3).tolist()}")
        print(f"Sample Pred IDs: {pred_df['Story_ID_str'].head(3).tolist()}")
        return

    correct = (results['label_num'] == results['Prediction']).sum()
    total = len(results)
    accuracy = (correct / total) * 100
    
    print(f"\n--- Validation Results ---")
    print(f"Total processed: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.2f}%")
    
    # Show some mismatches
    mismatches = results[results['label_num'] != results['Prediction']]
    if not mismatches.empty:
        print("\nTop 3 Sample Mismatches:")
        for _, row in mismatches.head(3).iterrows():
            print(f"- ID {row['id']} ({row['char']}): True={row['label']}, Pred={row['Prediction']}")
            print(f"  Rationale: {row['Rationale'][:200]}...")

if __name__ == "__main__":
    calculate_accuracy()
