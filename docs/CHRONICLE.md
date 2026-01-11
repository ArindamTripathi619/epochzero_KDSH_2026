# Development Chronicle: Narrative Consistency Classification
## Team: epochzero | Final Accuracy: 63.75%

This document summarizes the experiments, failures, and achievements of the KDSH 2026 development process.

---

## 1. Achievements (The Winning Strategy)

We successfully built a robust, scalable Pathway-based pipeline that reasons over long-form narratives with **63.75% accuracy** (validated on the 80-row train set).

### Key Breakthroughs:
- **Dual-Pass "Defense Attorney" Reasoning**: We implemented a two-stage LLM process. The second pass acts as a defense attorney for the backstory, requiring **irrefutable proof** to sustain a contradiction. This successfully neutralized the LLM's natural "hallucination bias" towards finding conflicts.
- **Robust Character Mapping**: We moved away from strict filename matching to a word-based, normalized filtering logic in the `combine_evidence` UDF. This ensured that characters with spaces or underscores in their names (e.g., "Jacques Paganel") correctly retrieved their respective novel evidence.
- **High-Recall Retrieval ($k=50$)**: By significantly increasing the context window (50 chunks), we ensured that subtle causal contradictions spread across multiple chapters were available for LLM synthesis.
- **JSON Standardized Pipeline**: Standardizing communication between LLMs and Pathway via strict JSON objects resolved a major parsing regression and allowed for reliable processing of the final 0/1 labels.

---

## 2. Experiments & Failures (What We Learned)

### Feature: Evidence Reranking
- **Experimental Setup**: A custom reranker prioritized chunks containing negation keywords ("not", "never", "instead") or character names.
- **Result**: **FAILURE**. While it found conflicts faster, it often pulled out-of-context sentences that *looked* like contradictions but were actually figures of speech or silent periods. This lowered precision and led to false positives.

### Feature: Local LLM (Mistral-7B)
- **Experimental Setup**: Attempted to run the pipeline using a local Ollama instance with Mistral to reduce cost.
- **Result**: **FAILURE (~35% accuracy)**. The local model struggled with the specialized 'Dossier' output format and failed to maintain global narrative constraints over 15+ evidence chunks.

### Feature: Atomic Claim Verification (The "Safalta" Experiment)
- **Experimental Setup**: Decomposed the backstory into 8 granular claims and verified each independently using Noisy-OR scoring.
- **Result**: **FAILURE (~55% accuracy)**. The system lost the "big picture." Small individual consistent claims didn't aggregate effectively to verify global causal impossibility.
- **Pivot Point**: This experiment was pivotal because it exposed critical bugs in our character-novel evidence association, leading to the **Robust Mapping** fix that ultimately boosted our global reasoning performance.

---

## 3. Final Pipeline Architecture

The final system (available in the `submission.zip`) utilizes:
1.  **Pathway Vector Store**: For high-speed semantic retrieval.
2.  **Adaptive k-Retrieval**: Selecting context depth based on backstory complexity.
3.  **Unified Global Reasoning**: Synthesis of all 50 evidence chunks in a single high-context dual-pass.
4.  **Self-Correction Stage**: The Lead Editor pass that enforces the "Silence != Contradiction" rule.

---

### Final Stats:
- **Accuracy**: 63.75% (51/80)
- **Labeling**: 1 (Consistent), 0 (Contradict)
- **Format**: Dossier-style rationale with direct verbatim excerpts.
