# Judge Strategy: "Balanced Aggression" V3

This document covers the advanced NLI-jury architecture used to achieve the 69.01% accuracy breakthrough in the Narrative Consistency project.

## 1. The Core Challenge: The "Consistency Trap"
Standard LLMs (even GPT-4o) exhibit a strong bias toward labeling backstories as **CONSISTENT** (Label 1) because contradictions are often subtle and require deep timeline cross-referencing.

## 2. "Balanced Aggression" Architecture
We implemented a two-tier rule-based jury in `src/models/llm_judge.py`:

### Tier 1: The Groq Ensemble (Base Jury)
Three highly efficient models on Groq are queried in parallel via `ThreadPoolExecutor`:
- **Llama 3.3 70B**: Strong logical reasoning and grounding.
- **Qwen 2.5 72B**: Excellent at following complex multi-constraint prompts.
- **Kimi 1.5 120B**: Deep contextual understanding for long stories.

The and-group result is determined by a majority vote (>= 2/3).

### Tier 2: The Devil's Advocate (Arbitrator)
We query a fourth model (**GPT-OSS-1.5-120B**) for an intensive "stress test" pass.

#### The DA Mandate:
- **SCORE**: Provide a `CONTRADICTION_SCORE` from 1-10 (1=Perfectly Consistent, 10=Blatant Contradiction).
- **QUOTE**: Mandatory requirement to include a `DIRECT_QUOTE` from the source evidence. Without a quote, the contradiction is dismissed.

## 3. The Override Engine
The DA has the power to override the ensemble under strict logical conditions:

| Ensemble Verdict | DA Score | Action | Rationale |
|------------------|----------|--------|-----------|
| **Consistent** (Label 1) | **Score >= 8** (+ Quote) | **OVERRIDE to 0** | The DA found strong evidence the ensemble missed. |
| **Contradictory** (Label 0) | **Score <= 3** | **OVERRIDE to 1** | The ensemble was overly aggressive on weak evidence. |
| **Consistent** (Label 1) | **Score 4-7** | Keep 1 | Evidence is too ambiguous for override. |

## 4. Key Improvements & Accuracy
- **Baseline**: 64% - 66% (Single Model)
- **V2 (Ensemble Only)**: 68.75%
- **V3 (Balanced Aggression)**: **69.01%**

The breakthrough came from the DA's ability to "pessimistically verify" contradictions, resolving the common false-negative (missed contradiction) pattern.
