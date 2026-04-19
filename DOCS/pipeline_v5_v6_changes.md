# Pipeline V5 and V6 Changes Report

## Overview
This document summarizes the architectural and stability upgrades introduced to the Narrative Consistency Pipeline after commit `4c789b8`. These changes encompass "Strategy 3" and "Strategy 6" integrations, collectively forming the **V5.0** to **V6.0** pipeline, to vastly improve logic verification against long context and eliminate `429 Too Many Requests` crashes during 14+ hour runs.

## Key Changes & Explanations

### 1. Robust Rate-Limiting & Anti-Crash Mechanisms 
The most widespread changes deal with keeping the pipeline alive during exhaustive batch runs without crashing from 429 API errors on Groq and OpenRouter.
*   **Time Jittering:** A dynamic pacing system (`time.sleep(random.uniform(0.1, 5.0))` and `random.uniform(2.0, 15.0)`) was added throughout `main.py` and `llm_judge.py`. This purposely staggers API requests, preventing "bursts" of concurrent hits that immediately trigger provider rate limits based on tokens-per-minute constraints.
*   **Timeouts Extended:** The request timeout limits for the helper models (such as Identity Extraction and Claim Decomposition) were expanded from 10/15 seconds to a full 60 seconds to accommodate slow inference times under load.
*   **Verbose Logging:** `llm_judge.py` now includes a heavily detailed `[LLM-CALL START/END/ERROR]` logging system with precise time-stamps. This ensures total transparency and debugging capability during background `nohup` sessions in `pipeline_v6.log`.
*   **Calibrated Exponential Backoff:** The retry logic in the Judge was strengthened. If it detects a `429` error, it uses a specialized `(2^attempt) + 5` second backoff, explicitly allowing models to naturally exit their cooldown periods without crashing the static Pathway loop.

### 2. Strategy 3: DA-Guided "Targeted" Re-Retrieval
This is a major algorithmic upgrade to how the Judge retrieves evidence in `main.py`. It tackles Issue #2, where high disagreement between the ensemble and the Devil's Advocate (DA) led to incorrect verdicts due to missing context.
*   If the Devil's Advocate module gives an "ambiguous" or conflicting score (between `5` and `7`), the pipeline now pauses the standard judgment flow.
*   It utilizes Regex to extract the specific quote or phrase the DA was uncertain about.
*   It then invokes a local HuggingFace bi-encoder (`sentence-transformers/all-MiniLM-L6-v2`) to perform a **targeted semantic search** across *all* available story evidence just for that specific sub-claim.
*   It grabs the Top-5 most relevant hits, injects them into the prompt as augmented `[TARGETED]` evidence, and forces the LLM Jury to completely re-judge the case.

### 3. V5.0 Hierarchical Plot Map Integration
*   The previous approach involved dynamic generation of mini plot summaries per story using `groq-scout`. This was unstable and slow.
*   The dynamic generation was entirely removed. Instead, the framework now pre-loads static `_plot_map.txt` files directly from `Dataset/PlotMaps/` into memory. 
*   This hierarchical, book-level global context map is now reliably directly injected into the `ConsistencyJudge` prompts to maintain accurate character relationships across complex narratives.

### 4. Model Ensemble Roster Swap
The jury roster in `llm_judge.py` was completely overhauled to use higher-capacity, more stable models.
*   **The Main Ensemble** shifted from `["groq-llama", "groq-qwen", "groq-kimi"]` to a mixed-provider setup: `["groq-llama", "or-trinity", "or-nemotron-9b"]`.
*   **The Devil's Advocate** was swapped from `groq-gpt-oss` to `groq-qwen`.
*   **DA Scoring Thresholds:** The Devil's Advocate override system was re-calibrated. It now overrides the Jury to "Contradictory" if its score is `7+` (previously `8+`), and overrides them to "Consistent" if the score is `4-` (previously `3-`). This reduces over-aggression.

### 5. Dependency & Environment Fixes (Python 3.14 Compatibility)
Both `main.py` and `verify_judge.py` received a mocked bypass for the `beartype` library. Python 3.14 breaks `beartype`, which internally causes the Pathway Engine to crash. The code now catches `BeartypeDecorHintNonpepException`, `BeartypeCallHintParamViolation`, and `BeartypeCallHintViolation`, mocking them seamlessly so the pipeline runs perfectly on standard Linux instances without dependency downgrades.

## Results achieved on V6 run
After deploying these optimizations, Stage 1 (employing Qwen-32B as the Devil's Advocate) achieved the following performance metrics during a 14-hour continuous batch run:

*   **Completion Rate:** 100% (80 out of 80 stories processed successfully)
*   **System Stability:** 0 application crashes (all 429 rate limit events were successfully mediated through backoff)
*   **Correct Predictions:** 54
*   **Incorrect Predictions:** 26
*   **Final Verified Accuracy:** **67.50%**

While stability is absolute, the false positive rate indicates that Qwen-32B is slightly too lenient as a Devil's Advocate. As a result, the next planned stage (Stage 2) involves swapping the DA role to the higher-reasoning `Llama-3.3-70B`.
