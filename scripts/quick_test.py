#!/usr/bin/env python3
"""Quick single experiment runner to get accuracy"""
import subprocess
import pandas as pd
import sys
import os

if len(sys.argv) > 1:
    flags = sys.argv[1:]
else:
    flags = []  # Baseline case

# Clear previous results
if os.path.exists("results.csv"):
    os.remove("results.csv")

# Run experiment
env = os.environ.copy()
env["INPUT_DATA"] = "Dataset/ablation_subset.csv"
env["USE_CLOUD"] = "True"

cmd = ["python", "main.py"] + flags
subprocess.run(cmd, env=env)

# Calculate accuracy
train_df = pd.read_csv('Dataset/ablation_subset.csv')
train_df['label_num'] = train_df['label'].map({'consistent': 1, 'contradict': 0})

pred_df = pd.read_csv('results.csv')

train_df['id_str'] = train_df['id'].astype(str)
pred_df['Story_ID_str'] = pred_df['Story ID'].astype(str)

results = pd.merge(train_df, pred_df, left_on='id_str', right_on='Story_ID_str')
results['Prediction'] = pd.to_numeric(results['Prediction'], errors='coerce').fillna(1).astype(int)

correct = (results['label_num'] == results['Prediction']).sum()
total = len(results)
accuracy = (correct / total) * 100 if total > 0 else 0

print(f"\n{'='*50}")
print(f"RESULT: {accuracy:.1f}% ({correct}/{total})")
print(f"{'='*50}")
