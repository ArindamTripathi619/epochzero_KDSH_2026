# Development History — The Road to 68.75% Accuracy

This document outlines the major architectural shifts, hardships, and design decisions made during the evolution of the narrative consistency pipeline.

## 1. The "JSON Trap" (Early Hardship)

**Problem**: Forcing the LLM to output structured JSON significantly degraded reasoning quality. The model would prioritize formatting over logic, leading to "over-conservative" results.

**Solution**: Switched to **Chain-of-Thought (CoT)** prompting. We removed the JSON constraint, allowing DeepSeek R1 to "think" as much as it needed before committing to a final `VERDICT` tag. 

## 2. The NLI Reranking Pivot (Strategy 4)

**Problem**: NLI models (DeBERTa) were initially used as primary judges but produced too many False Positives (over 40%). Conversely, raw vector search often missed the "smoking gun" evidence in large chapters.

**Solution**: Repositioned NLI as a **Passive Reranker**. We used the NLI Cross-Encoder to reshuffle the Top-100 vector-search results, ensuring that the best evidence was in the Top-20 window for the LLM. 100% of final verdicts shifted to the LLM (Strategy 4), which pushed accuracy from 63% to 68.75%.

## 3. Metadata Grounding Hurdles

**Hardship**: We attempted an **Entity Grounding** fix by passing specific character names to the LLM. 
**Result**: Accuracy dropped to 65.00%. 
**Discovery**: We identified that ~15% of the `train.csv` character assignments are incorrect (e.g., backstory for Jacques Paganel mislabeled as "Thalcave"). Giving the LLM the "wrong" character name caused it to ignore valid evidence. We successfully reverted to a **Pure-Text reasoning** model to bypass this metadata noise.

## 4. Context Dilution Plateau

**Hardship**: We tested expanding the evidence window from 20 to 25 snippets.
**Result**: Accuracy dropped to 63.75%. 
**Lesson**: Increasing context beyond 20 snippets introduces "noise" that drowns out the contradiction and causes the LLM to hallucinate consistency. **Top-20 Reranked** is the definitive sweet spot for DeepSeek R1.

## Final Milestone: 69.01% (49/71) - THE BREAKTHROUGH
We reached a new state-of-the-art at 69.01% using Strategy 5: **Balanced Aggression**. This architecture uses a Groq-based model ensemble (Llama 3.3, Qwen 2.5, Kimi 1.5) combined with a high-capacity **Devil's Advocate** (GPT-OSS 1.5) to arbitrate split decisions and stress-test consistency.

**Success Factor**: The addition of a `CONTRADICTION_SCORE` (1-10) and a mandatory `DIRECT_QUOTE` requirement for overrides successfully eliminated the false-negative bias that plagued Strategy 4.
