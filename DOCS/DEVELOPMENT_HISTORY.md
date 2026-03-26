# Development History — The Road to 65% Accuracy

This document outlines the major architectural shifts, hardships, and design decisions made during the stabilization of the narrative consistency pipeline.

## 1. The "JSON Trap" (Early Hardship)

**Problem**: Forcing the LLM to output structured JSON (`response_format={"type": "json_object"}`) significantly degraded reasoning quality. The model would often prioritize the output format over the logic, leading to "over-conservative" results (defaulting to Consistent).

**Solution**: Switched to **Chain-of-Thought (CoT)** prompting. We removed the JSON constraint and implemented a manual parser to extract the `VERDICT: [LABEL]` tag. This allowed the model to "think" as much as it needed before committing to a label.

## 2. NLI Threshold Pitfalls

**Problem**: The `nli-deberta-v3-small` model is fast but prone to noise. 
- **Relaxed Thresholds (0.82/0.75)**: Caught 21/29 real contradictions but produced **40 False Positives**, dropping accuracy to 40%.
- **Architecture Reversal**: Trusting NLI directly (without LLM override) failed because of this low precision.

**Decision**: Reverted to **High-Confidence NLI Flags (0.90) + LLM Override**. This ensures the LLM applies its "common sense" wisdom to NLI-flagged contradictions, which is where the 65% accuracy plateau is currently held.

## 3. Propagation of Metadata

**Hardship**: Propagating chapter metadata correctly across the Pathway compute graph was critical for giving the LLM context. Without "Chapter X" headers, the LLM struggled to determine if events happened at different times or if they truly conflicted.

## 4. Why We Stayed with Hybrid (NLI + LLM)

We considered an **LLM-First** approach (sending all 80 stories to LLM), but stayed with the **NLI-Filter** for three reasons:
1. **Cost/Speed**: NLI filtering reduces LLM calls by 60%.
2. **Precision**: High-confidence NLI flags provide a grounded "seed" for the LLM to verify.
3. **Reproducibility**: Local NLI acts as a deterministic anchor for the stochastic LLM.

## Lessons Learned
- **Prompt Safety**: Passing NLI rationale to the LLM introduced *Confirmation Bias*. Giving the LLM raw evidence for independent judgment improved accuracy.
- **Temporal Reasoning**: Pure NLI models are terrible at years. A secondary regex check for temporal clashes is a high-accuracy mandatory component.
