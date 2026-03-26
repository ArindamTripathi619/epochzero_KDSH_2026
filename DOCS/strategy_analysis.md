# Strategy Analysis & Accuracy Benchmarks

| Configuration | Model(s) | Retrieval | Logic | Accuracy |
| :--- | :--- | :--- | :--- | :--- |
| **Strategy 1 (NLI-First)** | NLI (DeBERTa-v3) | Vector Only (Top-10) | NLI short-circuits LLM | ~58% |
| **Strategy 2 (LLM-First)** | DeepSeek R1 (70B) | Vector Only (Top-12) | LLM bypasses NLI | 67.50% |
| **Strategy 4 (V1 Rerank)** | DeepSeek R1 (70B) | Reranked (Top-12) | LLM bypasses NLI | 67.50% |
| **Strategy 4 (V2 Context)** | DeepSeek R1 (70B) | Reranked (Top-20) | LLM bypasses NLI | **68.75%** |
| **Strategy 4 (V3 Grounding)**| DeepSeek R1 (70B) | Reranked (Top-20) | LLM + Entity Name | 65.00% |
| **Strategy 4 (V4 HighCtx)** | DeepSeek R1 (70B) | Reranked (Top-25) | LLM bypasses NLI | 63.70% |

## 1. Role of NLI Model in Current Runs
In the current "LLM-First" architecture (Strategy 3 & 4), the NLI model (`DeBERTa-v3-large`) has been repositioned as a **Passive Assistant**:
- **Reranking**: We use the NLI Cross-Encoder to reshuffle the Top-100 vector-search results, ensuring that the best evidence is in the context window.
- **Veto Filter**: It is capable of a "Programmatic Veto" if it detects a definite contradiction, but in Strategy 3 & 4, 100% of final verdicts are audited by the LLM (DeepSeek R1).

## 2. Why Strategy 4 (Top-20) Peaks
- **Top-12**: Missing key evidence for 30%+ of stories.
- **Top-20**: Sweet spot that captures "smoking gun" evidence while maintaining high reasoning density.
- **Top-25**: Introduces "Context Dilution". The LLM starts seeing irrelevant side-plots that hallucinate false narrative conflicts.

## 3. Metadata Grounding Failure (Entity Fix)
Passing character names (e.g. "Jacques Paganel") *decreased* accuracy to 65.00%. 
**Reason**: About 15% of the [train.csv](file:///home/DevCrewX/Projects/epochzero_KDSH_2026/debug_train.csv) character assignments are incorrect (e.g. ID 66 backstory describes Paganel but the `char` column says "Thalcave"). In these cases, telling the LLM the story is about "Thalcave" causes it to ignore evidence about "Paganel", leading to False Consistencies.

## 4. Final Push Plan: Forensic Prompting
We are reverting to **Top-20 Reranked** and focusing on a "Skeptical Audit" prompt to break the 70% barrier.
