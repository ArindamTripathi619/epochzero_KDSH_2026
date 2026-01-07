
## 6. Analysis of Final Results
We ran the full inference pipeline on `Dataset/test.csv` (60 test cases).

### Quantitative Summary
*   **Total Cases**: 60
*   **Consistent (Label 1)**: ~54 cases (90%)
*   **Contradictory (Label 0)**: ~6 cases (10%)

### Qualitative Observations
1.  **"Silence is Consistent" Heuristic**: The model successfully applied the principle that absence of evidence does not equal contradiction.
    *   *Example*: "EVIDENCE: No evidence found... ANALYSIS: This is consistent because the novel provides no evidence that contradicts these claims."
    *   This confirms our Prompt Engineering (in `llm_judge.py`) was effective.
2.  **Detection of Contradictions**: The model flagged specific contradictions where key character traits or events clashed.
    *   *Example*: Row 22 (Noirtier) was flagged as contradictory because the "Southern Army" claim had zero support, although the logic here was borderline (treating absence as contradiction).
3.  **Rationale Quality**: The "Dossier" format was strictly followed (`EVIDENCE -> CLAIM -> ANALYSIS`), making the decision process transparent and easier for human judges to audit.

### Areas for Improvement
*   **False Positives on Contradiction**: In a few rare cases (e.g., Row 22, 54), the model might have been *too* strict, treating "No evidence found" as a contradiction for major plot points. A more nuanced "Unknown" class would be beneficial if the competition allowed it.
