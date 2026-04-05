import pandas as pd
import os

def calculate_full_accuracy(pred_path='results.csv', truth_path='Dataset/train.csv'):
    """Calculate accuracy between predictions and ground truth."""
    try:
        if not os.path.exists(truth_path):
             # Try alternate path if not found
             truth_path = 'Dataset/train_fixed.csv'
             
        # Load Ground Truth
        truth_df = pd.read_csv(truth_path)
        # Map id -> label (Standard: 1=Consistent, 0=Contradict)
        # Handle different potential column names ('id' vs 'ID', 'label' vs 'Label')
        id_col = 'id' if 'id' in truth_df.columns else 'ID'
        label_col = 'label' if 'label' in truth_df.columns else 'Label'
        
        truth_map = {}
        for _, row in truth_df.iterrows():
            sid = str(row[id_col])
            val = row[label_col]
            # Convert string label to int
            if isinstance(val, str):
                label = 1 if val.lower() == 'consistent' else 0
            else:
                label = int(val)
            truth_map[sid] = label
        
        # Load Predictions
        if not os.path.exists(pred_path):
            print(f"Error: Prediction file {pred_path} not found.")
            return None
            
        print(f"\n--- Automated Accuracy Report ---")
        print(f"Loading predictions from: {pred_path}")
        # Preds from Pathway might have internal columns; read only necessary ones
        pred_df = pd.read_csv(pred_path, on_bad_lines='skip')
        
        correct = 0
        total = 0
        
        headers = f"{'Story ID':<10} {'Truth':<12} {'Pred':<10} {'Result'}"
        print(headers)
        print("-" * len(headers))

        for _, row in pred_df.iterrows():
            # Support both 'Story ID' and 'id'
            sid_key = 'Story ID' if 'Story ID' in row else 'id'
            if sid_key not in row: continue
            sid = str(row[sid_key])
                
            if sid not in truth_map:
                continue
                
            truth_label = truth_map[sid]
            
            # Handle prediction parsing
            try:
                # Remove quotes if they exist and convert to int
                raw_pred = str(row['Prediction']).replace('"', '').strip()
                pred_label = int(float(raw_pred))
            except (ValueError, TypeError):
                continue
            
            is_correct = (truth_label == pred_label)
            if is_correct:
                correct += 1
            total += 1
            
            status = "✅" if is_correct else "❌"
            t_str = "Cons" if truth_label==1 else "Contra"
            p_str = "Cons" if pred_label==1 else "Contra"
            print(f"{sid:<10} {t_str:<12} {p_str:<10} {status}")
            
        if total == 0:
            print("No matching IDs found between prediction and truth files.")
            return 0.0

        acc = (correct / total) * 100
        print("-" * len(headers))
        print(f"FINAL ACCURACY: {acc:.2f}% ({correct}/{total})")
        print(f"--- End of Report ---\n")
        return acc

    except Exception as e:
        print(f"Error in accuracy calculation: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import sys
    pred = sys.argv[1] if len(sys.argv) > 1 else 'results.csv'
    truth = sys.argv[2] if len(sys.argv) > 2 else 'Dataset/train.csv'
    calculate_full_accuracy(pred, truth)
