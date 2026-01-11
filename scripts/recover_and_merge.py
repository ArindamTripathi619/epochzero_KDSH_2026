import pandas as pd
import io

def recover_and_merge():
    print("Starting recovery and merge process...")
    
    # 1. Load Current Run (with errors)
    try:
        current_df = pd.read_csv("results.csv")
        # Filter out API errors
        valid_current = current_df[~current_df['Rationale'].astype(str).str.contains("API Error fallback", na=False)]
        print(f"Valid rows from Current Run: {len(valid_current)}")
    except Exception as e:
        print(f"Error reading current results: {e}")
        return

    # 2. Define Recovered Subset Results (from Step 3133 Log)
    # Story ID, Prediction (1=Cons, 0=Contra)
    # We will construct a minimal DF and merge with backup metadata if needed, 
    # but for now let's just use the prediction and a generic rationale if missing.
    # Actually, we can't easily valid Rationale from just "Cons/Contra" text.
    # But wait, we need the "Rationale" column for the CSV format.
    # We will fallback to 'results_merged.csv' for Rationale if possible, 
    # OR if the prediction differs, we might have to construct a placeholder?
    # No, let's look at Step 3133 again. It only shows Truth/Pred.
    # ID 46: Pred=Cons. Truth=Cons. 
    # Previous run (results_merged.csv) likely had Pred=Contra (0).
    # If I just copy the Rationale from the backup (which was for "Contra"), it will mismatch the new "Cons" prediction.
    # This is risky. 
    #
    # BETTER PLAN:
    # The 18 failures include ID 46. 
    # ID 46 was CORRECT in the subset run.
    # Just copying the label without rationale is bad form (DOSSIER format required).
    #
    # UPDATE:
    # Let's check which of the 18 failures are in the subset list.
    # Failures: 43, 113, 128, 35, 13, 18, 105, 99, 112, 19, 118, 12, 46, 36, 104, 84, 23, 40
    # Subset (Step 3133): 79, 67, 9, 31, 137, 12, 88, 13, 134, 109, 83, 18, 46, 55, 84, 68, 104, 35, 74, 112
    #
    # Intersection (Failed in Full, Present in Subset):
    # - 12 (Contra)
    # - 13 (Cons)
    # - 18 (Cons)
    # - 35 (Contra)
    # - 46 (Cons)
    # - 84 (Cons)
    # - 104 (Cons)
    # - 112 (Cons - WAIT, Step 3133 said 112 Pred=Cons, Truth=Contra => Wrong)
    #
    # For these overlapping IDs, I *could* use the subset prediction, BUT I don't have the generated Rationale text (it wasn't logged).
    # Without the Rationale string, I can't make a valid submission entry (it requires "EVIDENCE -> CLAIM -> LOGIC").
    # Creating a fake rationale is risky.
    #
    # DECISION:
    # I must use the `results_merged.csv` (Backup) for these 18 failures.
    # It allows me to end with a complete, valid file.
    # I lose the "optimization" for these 18, but I keep it for the other 62.
    # 62 optimized + 18 baseline is still better than 80 baseline.
    pass

    # 3. Load Backup
    backup_df = pd.read_csv("results_merged.csv")
    print(f"Backup rows: {len(backup_df)}")
    
    # Map valid current results
    # Use Story ID as Int for key
    final_map = {}
    
    # Priority 1: Valid Current
    for _, row in valid_current.iterrows():
        try:
            sid = int(row['Story ID'])
            final_map[sid] = row.to_dict()
        except Exception:
            pass
            
    # Priority 2: Backup (Fill gaps)
    fill_count = 0
    for _, row in backup_df.iterrows():
        sid = int(row['Story ID'])
        if sid not in final_map:
            final_map[sid] = row.to_dict()
            fill_count += 1
            
    print(f"Filled {fill_count} rows from backup.")
    
    # Construct Final DataFrame
    final_rows = list(final_map.values())
    final_df = pd.DataFrame(final_rows)
    
    # Sort
    final_df['Story ID'] = final_df['Story ID'].astype(int)
    final_df = final_df.sort_values('Story ID')
    
    print(f"Final Count: {len(final_df)}")
    
    # Save
    final_df.to_csv("final_submission/results.csv", index=False)
    print("Saved to final_submission/results.csv")

if __name__ == "__main__":
    recover_and_merge()
