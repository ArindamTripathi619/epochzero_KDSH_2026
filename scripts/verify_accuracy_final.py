import csv
import os

def load_ground_truth(filepath):
    truth = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                sid = int(row['id'])
                # Mapping: 'consistent' -> 1, 'contradictory' -> 0
                label_val = 1 if row['label'].strip().lower() == 'consistent' else 0
                truth[sid] = label_val
            except Exception as e:
                print(f"[WARN] Failed to parse truth row: {row}. Error: {e}")
    return truth

def load_predictions(filepath):
    preds = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        # results_final_benchmark.csv: Story ID, Prediction, Rationale, Confidence, time, diff
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row or not row[0].isdigit():
                continue
            try:
                sid = int(row[0])
                pred = int(row[1])
                # We use the LAST entry for each SID because Pathway appends re-retrieval results at the end
                preds[sid] = pred
            except Exception as e:
                pass
    return preds

def verify():
    truth_file = "Dataset/train_fixed.csv"
    results_file = "results_final_benchmark.csv"
    
    if not os.path.exists(truth_file) or not os.path.exists(results_file):
        print("Error: Missing files.")
        return

    truth = load_ground_truth(truth_file)
    predictions = load_predictions(results_file)
    
    correct = 0
    total = 0
    failures = []
    
    # We only evaluate the 80 stories that are in BOTH files
    for sid in sorted(truth.keys()):
        if sid in predictions:
            total += 1
            if truth[sid] == predictions[sid]:
                correct += 1
            else:
                failures.append((sid, truth[sid], predictions[sid]))
        else:
            print(f"[MISSING] Prediction for Story ID {sid} not found in results.")

    if total == 0:
        print("Error: No overlapping Story IDs found.")
        return

    accuracy = (correct / total) * 100
    print("-" * 40)
    print(f"VERIFICATION REPORT")
    print("-" * 40)
    print(f"Total Stories Found:   {total}")
    print(f"Correct Predictions:   {correct}")
    print(f"Incorrect Predictions: {len(failures)}")
    print(f"Final True Accuracy:   {accuracy:.2f}%")
    print("-" * 40)
    
    if failures:
        print("\nSample Failures (ID, True, Pred):")
        for f in failures[:5]:
            print(f"ID {f[0]}: Truth={f[1]} (1=Consist, 0=Contradict), Pred={f[2]}")

if __name__ == "__main__":
    verify()
