# Implementation Plan: KDSH 2026 - Pathway Consistency Challenge

This project aims to solve the narrative consistency problem using Pathway's RAG framework. We will implement Track A, focusing on efficient long-context retrieval and LLM-based reasoning.

## User Review Required

> [!IMPORTANT]
> - We will primarily use **Track A** as suggested in the plans.
> - We are using **Ollama** with the **Mistral** model for 100% local reasoning, as OpenRouter cloud quotas have been exhausted.
> - This ensures full data privacy and zero cost while maintaining high classification quality.
> - **Dependency Installation**: We need to install `pathway`, `pathway-llm-app`, and other DS libraries.

## Proposed Changes

### Environment & Setup
- [NEW] `requirements.txt`: Project dependencies.
- [NEW] `setup.py`: Basic package setup if needed.

### Data Layer (Pathway)
- [NEW] `src/pathway_pipeline/ingest.py`: Handles novel ingestion and CSV data loading.
- [NEW] `src/pathway_pipeline/retrieval.py`: Implements vector indexing and retrieval logic using Pathway.

### Reasoning Layer
- [NEW] `src/models/llm_judge.py`: Interface for LLM calls (Ollama/OpenAI) with consistency-focused prompts.
- [NEW] `src/models/classifier.py`: (Optional) Logic for the secondary classifier.

### Orchestration
- [NEW] `main.py`: Main entry point to run training or prediction.
- [NEW] `results.csv`: Final output file.

## Verification Plan

### Automated Tests
- `pytest tests/`: We will write unit tests for:
    - Text chunking logic.
    - Pathway data ingestion.
    - Prompt construction.
- `python main.py --mode predict --subset 5`: Run a small subset of the test data to verify end-to-end flow.

### Manual Verification
- Review retrieved snippets for a few examples in `train.csv` to ensure high relevance.
- Inspect `results.csv` rationales for logical consistency and "Dossier" style (Excerpts + Linkage + Analysis).
