# Development History — The Road to 70%+ Accuracy

This document outlines the major architectural shifts, hardships, and design decisions made during the evolution of the narrative consistency pipeline.

## 1. The "JSON Trap" (Early Hardship)
**Problem**: Forcing the LLM to output structured JSON significantly degraded reasoning quality. The model would prioritize formatting over logic.
**Solution**: Switched to **Chain-of-Thought (CoT)** prompting, allowing models to "think" before committing to a final `VERDICT` tag.

## 2. The NLI Reranking Pivot (Strategy 4)
**Problem**: NLI models (DeBERTa) produced too many False Positives (over 40%). Conversely, raw vector search often missed "smoking guns."
**Solution**: Repositioned NLI as a **Passive Reranker**. Used NLI Cross-Encoder to reshuffle Top-100 results to a refined Top-20 window for the LLM. Accuracy shifted from 63% to 68.75%.

## 3. Metadata Grounding Hurdles (Resolved in V4.0)
**Hardship**: Initial attempts at Entity Grounding failed (65% accuracy) because ~15% of the `train.csv` character assignments were incorrect. 
**Final Solution (Strategy 6)**: Implemented **Identity extraction at runtime**. By extracting the character name from the backstory text itself using `groq-llama-small`, we bypassed noisy metadata and achieved 70%+ accuracy through correct grounding.

## 4. Context Dilution Plateau
**Hardship**: Testing expanded evidence windows (25+ snippets) caused accuracy to drop (63.75%). 
**Lesson**: **Top-20 Reranked** is the definitive "sweet spot." More context introducted "noise" that drowned out contradictions.

## 5. Milestone: 69.01% (Balanced Aggression)
Reached 69.01% using Strategy 5: **Balanced Aggression**. This architecture used a Groq ensemble (Llama 3.3, Qwen 2.5, Kimi 1.5) and a high-capacity **Devil's Advocate** (GPT-OSS 1.5) to arbitrate decisions.

## 6. Final Milestone: 70%+ (Identity-Grounded Ensemble)
**The Final Breakthrough**: By stacking **Strategy 6 (Identity Extraction)** on top of **Balanced Aggression**, we resolved the remaining 15% data quality overhead. We also automated the entire lifecycle using Pathway **Static Mode**, creating a "One-Click" pipeline that executes inference and produces an accuracy report automatically.
