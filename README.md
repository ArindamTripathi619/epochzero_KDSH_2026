# EpochZero Narrative Consistency Pipeline

A hybrid RAG-based classification system for detecting narrative contradictions in historical fiction and literary classics.

## Current Accuracy: **65.00%** (52/80)

## System Overview

This project uses **Pathway** for high-performance vector retrieval and a two-stage reasoning pipeline:
1. **NLI Filter**: High-recall candidate flagging using `nli-deberta-v3-small`.
2. **LLM Verification**: High-precision chain-of-thought verification using local **Groq/Llama-3** via the LiteLLM Rotator.

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Environment Setup**:
   Copy `.env.example` to `.env` and configure your LLM endpoint.
3. **Run Pipeline**:
   ```bash
   python main.py
   ```

## Documentation

For deep dives into the technical details, see the `DOCS/` directory:
- [Architecture & Workflow](DOCS/ARCHITECTURE.md): Mermaid diagrams and component breakdown.
- [Development History](DOCS/DEVELOPMENT_HISTORY.md): Hardships, triumphs, and the road to 65% accuracy.

## Recent Updates
- Transitioned to **Chain-of-Thought (CoT)** reasoning for the LLM judge.
- Implemented **Temporal Consistency** checks for year-based contradictions.
- Optimized **Pathway** retrieval with a cross-encoder reranker (k=12).
