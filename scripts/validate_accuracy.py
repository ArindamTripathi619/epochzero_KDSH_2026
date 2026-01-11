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
    os.environ["INPUT_DATA"] = "Dataset/train.csv"
    os.system("./venv/bin/python3 main.py")
    
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
