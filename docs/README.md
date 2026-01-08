# KDSH 2026 - Narrative Consistency Classification

**Team**: epochzero  
**Track**: A (Systems Reasoning with NLP and Generative AI)  
**Approach**: RAG-based pipeline with Pathway + Local LLM

## Project Overview

This project implements a **Retrieval-Augmented Generation (RAG)** system to classify whether hypothetical character backstories are consistent with long-form narratives (novels). The solution leverages:

- **Pathway Framework**: For document ingestion, vector indexing, and retrieval
- **SentenceTransformers**: For semantic embeddings
- **Mistral LLM** (via Ollama): For consistency reasoning
- **Chapter-Aware Splitting**: To preserve temporal metadata
- **"Silence != Contradiction"**: Conservative reasoning heuristic

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Ensure Ollama is running
ollama pull mistral

# 3. Run inference
./run_inference.sh

# 4. Check output
head results.csv
```

## Key Results

- **Validation Accuracy**: 62.5% (50/80 correct on `train.csv`)
- **Error Pattern**: Conservative (predicts Consistent when evidence is missing)
- **Compliance**: ✅ Numeric IDs, ✅ Dossier rationale, ✅ Pathway integration

## Documentation

Our comprehensive documentation is organized as follows:

### 📘 [01_Architecture_Overview.md](docs/01_Architecture_Overview.md)
**What**: System design, components, and data flow  
**For**: Understanding the high-level architecture  
**Highlights**:
- RAG pipeline diagram
- Component descriptions (NarrativeRetriever, ConsistencyJudge)
- Design decisions (why RAG, why k=15, why local LLM)
- Track A compliance checklist

### 🐛 [02_Debugging_Journey.md](docs/02_Debugging_Journey.md)
**What**: Technical challenges and solutions  
**For**: Learning from our debugging process  
**Highlights**:
- **Critical Issue #1**: Pathway ID pointer problem (and the fix)
- **Critical Issue #2**: Retrieval effectiveness (k=5 → k=15)
- **Critical Issue #3**: Chapter detection robustness
- **Critical Issue #4**: Validation implementation
- **Critical Issue #5**: Performance bottleneck analysis

### ✅ [03_Validation_Analysis.md](docs/03_Validation_Analysis.md)
**What**: Validation methodology and results  
**For**: Understanding model accuracy and behavior  
**Highlights**:
- 62.5% accuracy on `train.csv`
- "Silence != Contradiction" error analysis
- Problem Statement alignment justification
- ID bug fix verification

### ⚡ [04_Performance_Analysis.md](docs/04_Performance_Analysis.md)
**What**: Runtime profiling and optimization strategies  
**For**: Understanding bottlenecks and trade-offs  
**Highlights**:
- Embedding phase: 2-5 minutes (CPU-bound)
- LLM inference: 15-20 minutes (dominant bottleneck)
- Comparison: Local vs. Cloud LLM (10x speedup)
- Optimization roadmap

### 🛠️ [05_Implementation_Guide.md](docs/05_Implementation_Guide.md)
**What**: Code structure, usage, and troubleshooting  
**For**: Running, modifying, and debugging the system  
**Highlights**:
- Quick start guide
- Code walkthrough (main.py, retrieval.py, llm_judge.py)
- Configuration options (k, LLM, chunking)
- Common issues and fixes

### 📚 Additional Documentation

- **[Hackathon_Overview.md](docs/Hackathon_Overview.md)**: Original project context
- **[HACKATHON_COMPLETE_OVERVIEW.md](docs/HACKATHON_COMPLETE_OVERVIEW.md)**: Detailed hackathon requirements
- **[Project_Review_(Track A).md](docs/Project_Review_(Track A).md)**: External review and feedback

## Project Structure

```
KDSH/
├── main.py                          # Pipeline orchestration
├── run_inference.sh                 # Inference script
├── validate_accuracy.py             # Validation harness
├── package_submission.py            # Submission packager
├── requirements.txt                 # Dependencies
├── src/
│   ├── pathway_pipeline/
│   │   └── retrieval.py             # NarrativeRetriever
│   └── models/
│       └── llm_judge.py             # ConsistencyJudge
├── Dataset/
│   ├── Books/                       # Novels (.txt)
│   ├── train.csv                    # Labeled examples
│   └── test.csv                     # Submission queries
├── docs/                            # 📚 Documentation suite
│   ├── 01_Architecture_Overview.md
│   ├── 02_Debugging_Journey.md
│   ├── 03_Validation_Analysis.md
│   ├── 04_Performance_Analysis.md
│   └── 05_Implementation_Guide.md
├── submission/
│   └── Report/                      # Project report
└── results.csv                      # Output predictions
```

## Workflow

```
Input (test.csv)
    ↓
Pre-processing (ID renaming)
    ↓
Pathway Ingestion (Books + Queries)
    ↓
Chapter-Aware Splitting
    ↓
Vector Embedding (SentenceTransformer)
    ↓
Retrieval (k=15 chunks per query)
    ↓
Evidence Aggregation (Book filtering)
    ↓
LLM Judgment (Mistral via Ollama)
    ↓
Post-processing (Clean metadata)
    ↓
Output (results.csv)
```

## Key Features

### 1. Chapter-Aware Splitting
Preserves narrative structure and temporal metadata:
```
[Chapter 5 | 42%] Content...
```

### 2. Book-Specific Filtering
Ensures evidence comes only from the target novel:
```python
if target_book_lower not in chunk_path:
    continue  # Skip chunks from other books
```

### 3. Conservative Reasoning
"Silence != Contradiction" heuristic:
- If no evidence found → Predict Consistent
- Only flag contradictions with explicit textual support

### 4. Numeric ID Preservation
Pre-processing hack to avoid Pathway pointer mapping:
```python
df_input.rename(columns={'id': 'story_id_numeric'})
```

## Dependencies

**Core**:
- `pathway-ai==0.17.1`: RAG framework
- `sentence-transformers==3.3.1`: Embeddings
- `pandas==2.2.3`: Data manipulation

**LLM**:
- `ollama`: Local Mistral inference
- `anthropic`: Cloud Claude API (optional)

**Utilities**:
- `requests==2.32.3`: Ollama API calls
- `python-dotenv==1.0.1`: Environment variables

## Performance

| Metric | Value |
|--------|-------|
| **Validation Accuracy** | 62.5% |
| **Total Runtime** (80 queries) | ~23 minutes |
| **Embedding Time** | 3-4 minutes |
| **LLM Inference** | 15-20 seconds/query |
| **Throughput** | 3.4 queries/minute |

## Lessons Learned

1.  **Framework Quirks**: Pathway's `id` column behavior is undocumented but critical
2.  **Validation is Essential**: Without it, we would have submitted broken results
3.  **Conservative Defaults Win**: False Positives > False Negatives for Track A
4.  **Documentation Matters**: Problem Statement examples caught the ID bug

## Future Improvements

- **GPU Acceleration**: 10x speedup for embeddings
- **Cloud LLM**: 10x speedup for inference
- **Adaptive k**: Use more chunks for longer backstories
- **Hybrid Retrieval**: Combine semantic + keyword search
- **Ensemble**: Multiple LLMs for higher accuracy

## Contact

**Team**: epochzero  
**Track**: A (Systems Reasoning)  
**Repository**: [GitHub Link]

## Acknowledgments

- **Pathway**: For the RAG framework and LLM-App templates
- **Ollama**: For local LLM inference
- **KDSH Organizers**: For the challenging problem statement

---

**For detailed technical information, see the [docs/](docs/) directory.**
