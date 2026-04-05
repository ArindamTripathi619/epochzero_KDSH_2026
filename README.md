# EpochZero Narrative Consistency Pipeline

A hybrid RAG-based classification system for detecting narrative contradictions in historical fiction and literary classics.

## Current Accuracy: **69.01%** (49/71) 🏆

## System Overview

This project uses **Pathway v23** for high-performance vector retrieval and a unified **Balanced Aggression** reasoning pipeline:
1. **NLI Reranker**: Cross-encoder (`ms-marco-MiniLM-L6-v2`) used for high-precision snippet re-ranking.
2. **Balanced Aggression Jury**: Multi-model ensemble (Llama 3.3, Qwen 2.5, Kimi 1.5) with a **Devil's Advocate** (GPT-OSS 1.5) for final arbitration and stress-testing.

## Quick Start

1. **Environment Compatibility (Python 3.14)**:
   This project is optimized for Python 3.14 on Arch Linux. A `beartype` monkey-patch in `main.py` is required for stability.
   
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt --only-binary=:all:
   ```
3. **Run Pipeline**:
   ```bash
   python main.py
   ```

## Documentation

For technical deep dives, see the `DOCS/` directory:
- [Pathway v23 Migration](DOCS/MIGRATION_V23.md): Refactoring from DocumentStore to VectorStoreServer.
- [Judge Strategy](DOCS/JUDGE_STRATEGY.md): Detailed breakdown of the "Balanced Aggression" ensemble and DA logic.
- [Environment Recovery](DOCS/ENVIRONMENT_RECOVERY.md): Stabilizing Python 3.14 with beartype patching.

## Recent Updates
- **v3.0 (April 2026)**: Achieved **69.01% accuracy** using the Balanced Aggression jury.
- **Migration**: Full adaptation to **Pathway v23** VectorStoreServer API.
- **Robustness**: Implemented reliable retry logic for high-concurrency LLM processing.
- **Timeline Verification**: Enforced `DIRECT_QUOTE` requirements for all contradiction overrides.
