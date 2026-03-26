# Narrative Consistency Pipeline — Architecture

## System Overview

The **EpochZero** pipeline is a high-precision hybrid reasoning engine designed for detecting narrative contradictions. Version 2.0 (Strategy 4) represents the performance peak, moving from NLI-controlled logic to a unified **LLM-First Audit** system.

```mermaid
graph TD
    A[Backstory Input] --> B[Pathway Ingestion]
    B --> C[Sentence Chunking & Vector Store]
    
    A --> D[Evaluation Stage]
    D --> E[Reranking cross-encoder/ms-marco-MiniLM-L-6-v2]
    E --> F[Top 20 Reranked Evidence Chunks]
    
    F --> G[DeepSeek R1 reasoning (70B)]
    G --> H[Final Verdict: CONSISTENT or CONTRADICTORY]
```

## Key Components

### 1. Ingestion & Retrieval (Pathway)
- **Pathway Vector Store**: Handles real-time indexing of novel chapters.
- **Reranker**: Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` to audit the top 100 vector-search results. This ensures that the "needle in the haystack" evidence is prioritized in the LLM's limited context window.
- **Context Window**: Optimized at **20 reranked snippets**.

### 2. NLI Reranking & Veto (Natural Language Inference)
- **Model**: `cross-encoder/nli-deberta-v3-small`.
- **Role**: In Strategy 4, NLI is purely a **reranking assistant**. It identifies the strength of evidence for each chunk, providing the LLM with focused, relevant reasoning material. 

### 3. LLM Verification (The Judge)
- **Model**: **DeepSeek R1** (70B Distill) via the local rotator.
- **Strategy**: **Mandatory LLM Audit**. Every story is verified by the LLM, bypassing previous NLI short-circuiting to eliminate false positives.
- **Logic**: The LLM uses Chain-of-Thought (CoT) to explicitly analyze narratological, temporal, and spatial clashes.

---

## Metric Tracking (Evolution)

| Phase | Strategy | Accuracy |
|---|---|---|
| **Baseline** | NLI Only | ~50% |
| **V1.0** | NLI-First (Llama-3 Audit) | 65.00% |
| **V2.0 (Current)** | **LLM-First (DeepSeek R1 + Top-20 Rerank)** | **68.75%** |
