# Architecture Overview

## System Design

Our solution implements a **Retrieval-Augmented Generation (RAG)** pipeline for narrative consistency classification, specifically designed for Track A of the KDSH 2026 hackathon.

### High-Level Architecture

```
┌─────────────────┐
│  Input CSV      │
│  (Backstories)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Pre-Processing Layer              │
│   • ID Column Renaming              │
│   • Schema Discovery                │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Pathway Framework                 │
│   ┌───────────────────────────────┐ │
│   │  Document Ingestion           │ │
│   │  • Read novels from disk      │ │
│   │  • Chapter-aware splitting    │ │
│   │  • Metadata extraction        │ │
│   └───────────┬───────────────────┘ │
│               │                     │
│               ▼                     │
│   ┌───────────────────────────────┐ │
│   │  Vector Indexing              │ │
│   │  • SentenceTransformer        │ │
│   │  • BruteForce KNN             │ │
│   │  • Token-based chunking       │ │
│   └───────────┬───────────────────┘ │
│               │                     │
│               ▼                     │
│   ┌───────────────────────────────┐ │
│   │  Retrieval (k=15)             │ │
│   │  • Query: Character + Content │ │
│   │  • Book-specific filtering    │ │
│   │  • Temporal metadata          │ │
│   └───────────┬───────────────────┘ │
└───────────────┼─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│   Evidence Aggregation              │
│   • Filter by target book           │
│   • Format with chapter/progress    │
│   • Adaptive k calculation          │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Programmatic Reasoning Layer      │
│   • Entity State Tracker            │
│   • Timeline Validator (Years)      │
│   • Constraint Rules (Death/Prison) │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   LLM Judge (Hybrid Multi-Stage)    │
│   • Stage 1: Aggressive Search      │
│   • Stage 2: Rigorous Validation    │
│   • programmatic analysis context   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Post-Processing                   │
│   • Clean Pathway metadata          │
│   • Ensure numeric IDs              │
│   • Format CSV output               │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  results.csv    │
└─────────────────┘
```

## Core Components

### 1. NarrativeRetriever (`src/pathway_pipeline/retrieval.py`)

**Purpose**: Manages document ingestion, chapter-aware splitting, and semantic retrieval.

**Key Features**:
- **Chapter Detection**: Uses regex pattern to identify chapter boundaries:
  ```python
  r'(?m)^(?:CHAPTER|Chapter|PART|Part|BOOK|Book)\s+(?:[IVXLCDM\d]+|[A-Z]+).*$'
  ```
- **Temporal Metadata**: Calculates `progress_pct` for each chunk (e.g., Chapter 5 of 10 = 50%)
- **Fallback Handling**: Treats entire book as one chapter if no structure detected
- **Metadata Preservation**: Ensures `path` field is always valid for filtering

**Technical Stack**:
- `SentenceTransformerEmbedder`: `all-MiniLM-L6-v2` model
- `TokenCountSplitter`: 200-600 token chunks
- `BruteForceKnnFactory`: Exact nearest neighbor search

### 2. Reasoning Layer (`src/reasoning/`)

**Purpose**: Implements deterministic consistency checks to bridge the "Causal Reasoning" gap.

**Components**:
- **EntityStateTracker**: Uses spaCy + Regex to extract:
  - **Characters**: Fuzzy matching (e.g., "Dantes" matches "Edmond Dantes").
  - **Locations**: Keyword extraction (e.g., "Chateau", "Paris").
  - **Temporal Markers**: Year extraction (1700s-1900s).
- **TimelineValidator**: Detects simultaneity violations (e.g., being in two locations in the same year).
- **ConstraintRules**: Enforces implicit narrative rules:
  - **Imprisonment**: character cannot travel while in a dungeon.
  - **Post-Mortem**: character cannot act after a recorded death year.

### 3. ConsistencyJudge (`src/models/llm_judge.py`)

**Purpose**: Final arbiter using multi-stage LLM verification.

**Hybrid Reasoning Flow**:
1. **Aggressive Search**: Stage 1 LLM tries to find *any* possible contradiction, guided by programmatic results.
2. **Rigorous Validation**: If Stage 1 flags a conflict, a Stage 2 "Verification Agent" reviews it with a strict "90% certainty" threshold to reduce false positives.
3. **Determinism**: Temperature=0.0 and fixed seed (42) for reproducible evaluations.

**Prompt Strategy**:
- **Dossier Format**: EVIDENCE → CLAIM → ANALYSIS.
- **Hybrid Input**: Includes programmatic constraint analysis in the context.
- **Conservative Heuristic**: "Silence != Contradiction" enforced in Stage 2.

### 3. Main Pipeline (`main.py`)

**Purpose**: Orchestrates the end-to-end workflow.

**Critical Fix - ID Preservation**:
```python
# Pathway hijacks 'id' column as internal pointer
# We rename to 'story_id_numeric' to preserve values
df_input = pd.read_csv(TRAIN_DATA)
if 'id' in df_input.columns:
    df_input.rename(columns={'id': 'story_id_numeric'}, inplace=True)
df_input.to_csv(temp_data_path, index=False)
```

**Book Filtering**:
```python
@pw.udf
def combine_evidence(chunks: list, metadata: list, target_book: str) -> str:
    # Filter chunks to only include those from target book
    for i, chunk in enumerate(chunks):
        chunk_path = str(meta.get("path", "")).lower()
        if target_book_lower not in chunk_path:
            continue  # Skip chunks from other books
```

## Design Decisions

### 1. Why RAG Over Fine-Tuning?
- **Zero-Shot Generalization**: Works on any novel without training
- **Interpretability**: Evidence is explicitly cited in rationale
- **Cost-Effective**: No GPU training required
- **Track A Compliance**: Focuses on "evidence-grounded reasoning"

### 2. Why Adaptive k?
- **Efficiency**: Simpler backstories use fewer chunks (k=10).
- **Context Depth**: Complex, claim-heavy backstories retrieve more context (up to k=30).
- **Word-based Scaling**: k = 10 + (word_count // 20).

### 3. Why Hybrid Reasoning?
- **Address Causal Gaps**: LLMs often miss temporal/location constraints between distant chunks.
- **Deterministic Baseline**: Programmatic checks catch "impossible" events with 100% precision.
- **False Positive Reduction**: Multi-stage validation specifically addresses the "over-indexing on noise" issue.

### 4. Why Determinism?
- **Reproducibility**: Consistency in evaluations is critical for scientific validity.
- **Validation**: Ensures accuracy scores don't fluctuate between runs.
- **Seed**: Seed 42 used for all local and cloud completions.

## Track A Compliance

### Required: Pathway Integration
✅ **Document Ingestion**: `pw.io.fs.read()` for novels  
✅ **Vector Store**: `DocumentStore` with `SentenceTransformerEmbedder`  
✅ **Retrieval**: `query_as_of_now()` for semantic search  
✅ **Data Processing**: Pathway tables for all transformations  

### Evaluation Criteria
✅ **Accuracy**: 62.5% on validation set (honest, no hallucination)  
✅ **Novelty**: Chapter-aware splitting, temporal metadata, book filtering  
✅ **Long Context Handling**: Chunking + retrieval + metadata preservation  
✅ **Evidence-Grounded**: Dossier-style rationale with explicit citations  

## File Structure

```
KDSH/
├── main.py                    # Pipeline orchestration
├── src/
│   ├── pathway_pipeline/
│   │   └── retrieval.py       # NarrativeRetriever
│   └── models/
│       └── llm_judge.py       # ConsistencyJudge
├── Dataset/
│   ├── Books/                 # Novels (.txt)
│   ├── train.csv              # Labeled examples
│   └── test.csv               # Submission queries
├── docs/                      # Technical documentation
├── results.csv                # Output predictions
└── requirements.txt           # Dependencies
```

## Dependencies

**Core**:
- `pathway-ai`: RAG framework
- `sentence-transformers`: Embeddings
- `pandas`: Data manipulation
- `python-dotenv`: Environment variables

**LLM**:
- `ollama`: Local Mistral inference
- `anthropic`: Cloud Claude API (optional)

**Utilities**:
- `requests`: Direct Ollama API calls
