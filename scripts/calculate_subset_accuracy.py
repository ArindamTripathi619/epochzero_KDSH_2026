import pandas as pd
import os

def calculate_accuracy():
    try:
        # Load Ground Truth
        truth_df = pd.read_csv('Dataset/ablation_subset.csv')
        truth_map = {str(row['id']): (1 if row['label'] == 'consistent' else 0) for _, row in truth_df.iterrows()}
        
        # Load Predictions
        pred_path = 'results_final_standardized.csv'
        if not os.path.exists(pred_path):
            pred_path = 'results.csv'
            
        pred_df = pd.read_csv(pred_path)
        
        correct = 0
        total = 0
        
        print(f"{'Story ID':<10} {'Truth':<12} {'Pred':<10} {'Result'}")
        print("-" * 45)

        for _, row in pred_df.iterrows():
            sid = str(row['Story ID'] if 'Story ID' in row else row['id'])
            if sid not in truth_map:
                continue
                
            truth_label = truth_map[sid]
            pred_label = int(float(row['Prediction']))
            
            is_correct = (truth_label == pred_label)
            if is_correct:
                correct += 1
            total += 1
            
            status = "✅" if is_correct else "❌"
            t_str = "Cons" if truth_label==1 else "Contra"
            p_str = "Cons" if pred_label==1 else "Contra"
            
            print(f"{sid:<10} {t_str:<12} {p_str:<10} {status}")
            
        acc = (correct / total) * 100
        print("-" * 45)
        print(f"Subset Standardized Accuracy: {acc:.2f}% ({correct}/{total})")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    calculate_accuracy()
