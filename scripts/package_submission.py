import os
import shutil
import zipfile

TEAM_NAME = "epochzero"
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
    
    # Corrected paths for helper scripts
    if os.path.exists("scripts/run_inference.sh"):
        shutil.copy("scripts/run_inference.sh", SUBMISSION_DIR)
    if os.path.exists("scripts/validate_accuracy.py"):
        shutil.copy("scripts/validate_accuracy.py", SUBMISSION_DIR)
    
    # 2. Docs
    print("Copying docs...")
    shutil.copytree("docs", os.path.join(SUBMISSION_DIR, "docs"))
    
    # 3. Report
    print("Copying report...")
    report_source = "submission/Report/Project_Report.md"
    if os.path.exists(report_source):
        shutil.copy(report_source, os.path.join(SUBMISSION_DIR, "Report.md"))
    else:
        print(f"WARNING: Report not found at {report_source}")

    # 3. Results
    print("Copying results...")
    if os.path.exists("results.csv"):
        shutil.copy("results.csv", os.path.join(SUBMISSION_DIR, "results.csv"))
    else:
        print("WARNING: results.csv not found!")

    # Zip
    print(f"Creating {ZIP_NAME}...")
    shutil.make_archive(SUBMISSION_DIR, 'zip', root_dir='.', base_dir=SUBMISSION_DIR)
    
    print("Done!")

if __name__ == "__main__":
    create_submission()
