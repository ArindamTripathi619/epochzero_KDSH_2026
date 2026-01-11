import pandas as pd
import os

def merge_results():
    print("Merging results...")
    
    # Load current partial results (high quality, 60 rows)
    current_df = pd.read_csv("results.csv")
    print(f"Current results: {len(current_df)} rows")
    
    # Load backup results (complete, 80 rows)
    backup_df = pd.read_csv("results_backup.csv")
    print(f"Backup results: {len(backup_df)} rows")
    
    # Create dictionary of current results for easy lookup
    # Normalize IDs to strings for robust matching
    current_map = {}
    for _, row in current_df.iterrows():
        sid = str(row['Story ID'])
        current_map[sid] = row.to_dict()
    
    # Prepare final list
    # Use backup as the BASE and override with CURRENT where available
    # This guarantees we process exactly the 80 IDs from the full backup
    final_rows = []
    
    for _, row in backup_df.iterrows():
        sid = str(row['Story ID'])
        if sid in current_map:
            # Override with new result
            final_rows.append(current_map[sid])
        else:
            print(f"Using backup for Story ID: {sid}")
            final_rows.append(row.to_dict())
            
    # Create DataFrame
    final_df = pd.DataFrame(final_rows)
    print(f"Final merged results: {len(final_df)} rows")
    
    # sort by Story ID (cast to int for proper sort)
    final_df['Story ID'] = final_df['Story ID'].astype(int)
    final_df = final_df.sort_values('Story ID')
    
    # Ensure exactly 80
    if len(final_df) != 80:
        print(f"WARNING: Expected 80 rows, got {len(final_df)}")
    
    # Save
    final_df.to_csv("results_merged.csv", index=False)
    print("Saved to results_merged.csv")

if __name__ == "__main__":
    merge_results()
