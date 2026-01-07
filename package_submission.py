import os
import shutil
import zipfile

TEAM_NAME = "TEAM_NAME"  # Replace with actual team name
SUBMISSION_DIR = f"{TEAM_NAME}_KDSH_2026"
ZIP_NAME = f"{SUBMISSION_DIR}.zip"

def create_submission():
    if os.path.exists(SUBMISSION_DIR):
        shutil.rmtree(SUBMISSION_DIR)
    os.makedirs(SUBMISSION_DIR)

    # 1. Code
    print("Copying code...")
    shutil.copytree("src", os.path.join(SUBMISSION_DIR, "src"))
    shutil.copy("main.py", SUBMISSION_DIR)
    shutil.copy("requirements.txt", SUBMISSION_DIR)
    shutil.copy("run_inference.sh", SUBMISSION_DIR)

    # 2. Report
    print("Copying report...")
    report_dest = os.path.join(SUBMISSION_DIR, "Report.md")
    shutil.copy("submission/Report/Project_Report.md", report_dest)

    # 3. Results
    print("Copying results...")
    if os.path.exists("results.csv"):
        shutil.copy("results.csv", SUBMISSION_DIR)
    else:
        print("WARNING: results.csv not found! Please run inference first.")

    # Zip
    print(f"Creating {ZIP_NAME}...")
    shutil.make_archive(SUBMISSION_DIR, 'zip', root_dir='.', base_dir=SUBMISSION_DIR)
    
    print("Done!")

if __name__ == "__main__":
    create_submission()
