# Judge Strategy: "Balanced Aggression" V4 (Final)

This document covers the advanced NLI-jury architecture and preprocessing fixes used to break the 70%+ accuracy threshold in the Narrative Consistency project.

## 1. The Core Challenge: The "Consistency Trap" & Metadata Noise
Standard LLMs exhibit a bias toward labeling backstories as **CONSISTENT** because contradictions are subtle. Furthermore, ~15% of the dataset contains **corrupted or generic metadata** (e.g., character labels like "Name" or the wrong character entirely), which leads to false contradictions during grounding.

## 2. Strategy 6: Identity Extraction (Preprocessing)
Before the consistency check, we now perform a dynamic identity extraction pass in `main.py`:
- **Model**: `groq-llama-small` (8B)
- **Action**: Extracts the *actual* character name from the backstory text.
- **Result**: The "ground truth" identity is passed to the judge, bypassing noisy CSV metadata. This ensures the judge is looking for the right person in the novel's evidence.

## 3. "Balanced Aggression" Architecture
We implemented a two-tier rule-based jury in `src/models/llm_judge.py`:

### Tier 1: The Groq Ensemble (Base Jury)
Three highly efficient models on Groq are queried in parallel via `ThreadPoolExecutor`:
- **Llama 3.3 70B**: Strong logical reasoning and grounding.
- **Qwen 2.5 72B**: Excellent at following complex multi-constraint prompts.
- **Kimi 1.5 120B**: Deep contextual understanding for long stories.

The base verdict is determined by a majority vote (>= 2/3).

### Tier 2: The Devil's Advocate (Arbitrator)
We query a fourth model (**GPT-OSS-1.5-120B**) for an intensive "stress test" pass.

#### The DA Mandate:
- **SCORE**: Provide a `CONTRADICTION_SCORE` from 1-10 (1=Perfectly Consistent, 10=Blatant Contradiction).
- **QUOTE**: Mandatory requirement to include a `DIRECT_QUOTE` from the source evidence. Without a quote, the contradiction is dismissed.

## 4. The Override Engine
The DA has the power to override the ensemble under strict logical conditions:

| Ensemble Verdict | DA Score | Action | Rationale |
|------------------|----------|--------|-----------|
| **Consistent** (Label 1) | **Score >= 8** (+ Quote) | **OVERRIDE to 0** | The DA found strong evidence the ensemble missed. |
| **Contradictory** (Label 0) | **Score <= 3** | **OVERRIDE to 1** | The ensemble was overly aggressive on weak evidence. |
| **Consistent** (Label 1) | **Score 4-7** | Keep 1 | Evidence is too ambiguous for override. |

## 5. Key Improvements & Accuracy
- **Baseline**: 64% - 66% (Single Model)
- **V2 (Ensemble Only)**: 68.75%
- **V3 (Balanced Aggression)**: 69.01%
- **V4 (Identity Grounding)**: **70%+ (Final Breakthrough)**

The breakthrough came from combining **semantic grounding (Identity Extraction)** with **pessimistic verification (DA)**.
