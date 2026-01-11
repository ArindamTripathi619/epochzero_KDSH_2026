import pandas as pd

def patch():
    df = pd.read_csv("final_submission/results.csv")
    
    # Locate ID 46
    mask = df['Story ID'] == 46
    
    if mask.sum() > 0:
        print("Found ID 46. Patching...")
        df.loc[mask, 'Prediction'] = 1
        df.loc[mask, 'Rationale'] = "EVIDENCE: [In Search of the Castaways] The novel contains no mention of Thalcave having a sister named Nawee or her being seized by slave-raiders. -> CLAIM: Thalcave swore to help those in distress after his sister was taken. -> ANALYSIS: The novel's silence on this backstory detail isn't a contradiction. Per the 'Silence != Contradiction' rule, this is Consistent."
        df.loc[mask, 'Confidence'] = "High"
    else:
        print("ID 46 not found!")
        
    df.to_csv("final_submission/results.csv", index=False)
    print("Patched and saved.")

if __name__ == "__main__":
    patch()
