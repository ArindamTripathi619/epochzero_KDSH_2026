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
│   • Handle missing metadata         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   LLM Judge (Mistral via Ollama)    │
│   • Dossier-style prompt            │
│   • "Silence != Contradiction"      │
│   • JSON output parsing             │
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

### 2. ConsistencyJudge (`src/models/llm_judge.py`)

**Purpose**: Determines narrative consistency using LLM reasoning.

**Prompt Strategy**:
- **Dossier Format**: EVIDENCE → CLAIM → ANALYSIS
- **Conservative Heuristic**: "Silence != Contradiction"
  - If no evidence found, default to "Consistent"
  - Only flag contradictions with explicit textual support
- **JSON Output**: Structured response with `label` and `rationale`

**LLM Configuration**:
- **Local**: Mistral via Ollama (default)
- **Cloud**: Claude 3.5 Sonnet (optional, via `.env`)

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

### 2. Why k=15 for Retrieval?
- **High Recall**: Ensures we don't miss critical evidence
- **Balanced Context**: ~3-5k words fits within LLM context window
- **Empirical Testing**: Increased from k=5 based on Project Review feedback

### 3. Why "Silence != Contradiction"?
- **Logical Soundness**: Absence of evidence ≠ evidence of absence
- **Hallucination Prevention**: Avoids false contradictions
- **Problem Statement Alignment**: "Conclusions should be supported by signals drawn from... the text"

### 4. Why Local LLM (Mistral)?
- **Data Privacy**: No external API calls with sensitive data
- **Cost**: Zero inference cost
- **Reproducibility**: Consistent results across runs
- **Trade-off**: Slower inference (10-20s per query vs. 1-2s for cloud)

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
