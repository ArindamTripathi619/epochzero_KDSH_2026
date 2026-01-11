# Implementation Details and Usage Guide

## Quick Start

### Prerequisites
```bash
# Python 3.13+
python3 --version

# Ollama installed and running
ollama --version
ollama pull mistral

# New requirements for hybrid reasoning
./venv/bin/python3 -m spacy download en_core_web_sm
```

### Installation
```bash
# Clone repository
git clone <repo-url>
cd KDSH

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### Running Inference

**Option 1: Shell Script (Recommended)**
```bash
./run_inference.sh
```

**Option 2: Direct Python**
```bash
# Use default (test.csv)
python3 main.py

# Use custom input
INPUT_DATA=Dataset/train.csv python3 main.py
```

**Option 3: Validation**
```bash
python3 validate_accuracy.py
```

### Output
- **File**: `results.csv`
- **Format**:
  ```csv
  Story ID,Prediction,Rationale
  1,1,EVIDENCE: ... CLAIM: ... ANALYSIS: ...
  2,0,EVIDENCE: ... CLAIM: ... ANALYSIS: ...
  ```

## Code Structure

### Main Pipeline (`main.py`)

**Entry Point**: `main()` function

**Flow**:
1.  **Pre-processing**: Rename `id` column to avoid Pathway pointer mapping
2.  **Initialization**: Create `NarrativeRetriever` and `ConsistencyJudge`
3.  **Query Loading**: Read CSV with Pathway schema discovery
4.  **Retrieval**: Fetch k=15 relevant chunks per query
5.  **Evidence Aggregation**: Filter and format retrieved chunks
6.  **LLM Judgment**: Send to Mistral for consistency decision
7.  **Post-processing**: Clean Pathway metadata, ensure numeric IDs
8.  **Output**: Write `results.csv`

**Key Functions**:

```python
@pw.udf
def combine_evidence(chunks: list, metadata: list, target_book: str) -> str:
    """
    Filters chunks to only include those from the target book.
    Formats with chapter and progress metadata.
    """
    # Book filtering logic
    if target_book_lower not in chunk_path:
        continue
    
    # Format: [Chapter 1 | 14%] Content...
    entry = f"[{chapter} | {progress}%]\n{str(chunk)}"
    return "\n---\n".join(formatted_evidence)

@pw.udf
def parse_label(result_js: str) -> int:
    """Extracts binary label from LLM JSON response."""
    data = json.loads(result_js)
    return int(data.get("label", 0))

@pw.udf
def parse_rationale(result_js: str) -> str:
    """Extracts rationale from LLM JSON response."""
    data = json.loads(result_js)
    return str(data.get("rationale", "No rationale provided"))
```
@pw.udf
def perform_programmatic_reasoning(backstory: str, chunks: list, metadata: list, target_book: str) -> str:
    """
    Executes deterministic consistency checks before LLM judging.
    
    Modules called:
    - EntityStateTracker: Parses backstory for years/locations/persons.
    - TimelineValidator: Checks for location-year simultaneity conflicts.
    - ConstraintRules: Enforces prison/death logic.
    
    Returns: JSON string with 'conflicts' list for LLM context.
    """
    return json.dumps(results)

### NarrativeRetriever (`src/pathway_pipeline/retrieval.py`)

**Purpose**: Manages document ingestion, chapter splitting, and retrieval.

**Key Methods**:

```python
def __init__(self, books_dir: str, embedder_model: str = "all-MiniLM-L6-v2"):
    """
    Initializes the retriever with:
    - Document ingestion from books_dir
    - Chapter-aware splitting
    - Vector indexing with SentenceTransformer
    """

def retrieve(self, queries_table: pw.Table, k: int = 5):
    """
    Retrieves k nearest chunks for each query.
    Returns table with retrieved_chunks and retrieved_metadata columns.
    """
```

**Key UDFs**:

```python
@pw.udf
def split_by_chapter(data: bytes, metadata: dict) -> list[tuple[str, dict]]:
    """
    Splits book into chapters using regex pattern.
    Calculates progress_pct for temporal metadata.
    Handles preamble and fallback cases.
    """
    chapter_pattern = r'(?m)^(?:CHAPTER|Chapter|PART|Part|BOOK|Book)\s+(?:[IVXLCDM\d]+|[A-Z]+).*$'
    matches = list(re.finditer(chapter_pattern, text))
    
    # Calculate progress for each chapter
    progress = round((start / total_len) * 100, 1)
    
    return chunks

@pw.udf
def ensure_path_in_metadata(meta: dict) -> dict:
    """
    Ensures metadata has valid 'path' field for filtering.
    Prevents null path errors.
    """
    if "path" not in meta or meta["path"] is None:
        meta["path"] = "Unknown"
    return meta
```

### Reasoning Engine (`src/reasoning/`)

**Purpose**: Bridges the causal reasoning gap with deterministic checks.

- **`entity_tracker.py`**: Extracts years, locations, and persons using spaCy and keyword fallbacks.
- **`timeline_validator.py`**: Detects if a character is in two places at once by comparing backstory claims against narrative state chunks sharing the same year.
- **`constraint_rules.py`**: Enforces physical impossibilities:
    - **Imprisonment**: If narrative snippet contains prison keywords, character cannot be in an external location in the same year.
    - **Death**: If character is marked as dead in a year, backstory cannot claim activities in later years.

### ConsistencyJudge (`src/models/llm_judge.py`)

**Purpose**: Determines narrative consistency using LLM reasoning.

**Key Methods**:

```python
def __init__(self, use_cloud: bool = False, model_name: str = "mistral"):
    """
    Initializes judge with either:
    - Local Ollama (use_cloud=False)
    - Cloud API (use_cloud=True, requires .env)
    """

def judge(self, prompt_table: pw.Table) -> pw.Table:
    """
    Applies LLM to each prompt in the table.
    Returns table with 'result' column containing JSON response.
    """
```

**Prompt Building**:

```python
def build_consistency_prompt(backstory: str, character: str, evidence: str) -> str:
    """
    Constructs Dossier-style prompt:
    
    EVIDENCE: [Retrieved chunks with chapter/progress]
    CLAIM: [Backstory content]
    ANALYSIS: [Your reasoning]
    
    OUTPUT (JSON):
    {
      "label": 1 or 0,
      "rationale": "EVIDENCE: ... CLAIM: ... ANALYSIS: ..."
    }
    """
```

**LLM Call (Local)**:

```python
response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "mistral",
        "prompt": prompt,
        "stream": False
    }
)
```

## Configuration

### Environment Variables (`.env`)

```bash
# Optional: Cloud LLM API key
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Custom input file
INPUT_DATA=Dataset/train.csv
```

### Retrieval Parameters

```python
# main.py
retrieved_results = retriever.retrieve(query_table, k=15)
```

**Tuning `k`**:
- **k=5**: Faster, but may miss evidence
- **k=15**: Balanced (current setting)
- **k=30**: Comprehensive, but slower

### LLM Selection

```python
# main.py
judge = ConsistencyJudge(use_cloud=False, model_name="mistral")
```

**Options**:
- `use_cloud=False, model_name="mistral"`: Local Ollama
- `use_cloud=True`: Cloud Claude (requires `ANTHROPIC_API_KEY`)

### Chunking Parameters

```python
# retrieval.py
self.text_splitter = TokenCountSplitter(
    min_tokens=200,
    max_tokens=600,
    encoding_name="cl100k_base"
)
```

**Tuning**:
- **Smaller chunks** (200-400): More granular, but more chunks to retrieve
- **Larger chunks** (400-800): More context per chunk, but fewer chunks

## Troubleshooting

### Issue: "Ollama connection refused"

**Cause**: Ollama server not running.

**Fix**:
```bash
# Start Ollama
ollama serve

# In another terminal, pull model
ollama pull mistral
```

### Issue: "No matches found between train.csv and results.csv"

**Cause**: ID column mapping issue (should be fixed in current version).

**Verification**:
```bash
# Check if results.csv has numeric IDs
head -n 3 results.csv
# Should show: 1, 2, 3 (not ^ABC...)
```

**Fix**: Ensure `main.py` has the pre-processing hack:
```python
df_input.rename(columns={'id': 'story_id_numeric'}, inplace=True)
```

### Issue: "Pipeline appears stuck at 'Batches: 100%'"

**Cause**: CPU-bound embedding phase.

**Not a bug**: This is normal. The system is embedding the books.

**Wait time**: 2-5 minutes for 2 novels.

### Issue: "Out of memory"

**Cause**: Large book + high k value.

**Fix**:
1.  Reduce `k` from 15 to 10
2.  Reduce `max_tokens` in splitter from 600 to 400
3.  Use smaller embedding model

### Issue: "LLM returns invalid JSON"

**Cause**: Model occasionally outputs malformed JSON.

**Handled by**: `parse_label` and `parse_rationale` UDFs default to safe values.

**Debug**:
```python
# Add logging in llm_judge.py
print(f"LLM Response: {response_text}")
```

## Testing

### Unit Tests (`tests/`)

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_retrieval.py
```

### Validation Test

```bash
# Full validation on train.csv
python3 validate_accuracy.py

# Expected output:
# Accuracy: 62.50%
# Total processed: 80
```

### Sample Test

```bash
# Quick test on 5 queries
head -n 6 Dataset/train.csv > Dataset/sample.csv
INPUT_DATA=Dataset/sample.csv python3 main.py
```

## Submission Packaging

```bash
# Create submission ZIP
python3 package_submission.py

# Output: epochzero_KDSH_2026.zip
# Contains:
# - Code (src/, main.py, requirements.txt)
# - Report (submission/Report/)
# - Results (results.csv)
```

## Common Workflows

### Experiment with Different k Values

```python
# Edit main.py, line ~55
retrieved_results = retriever.retrieve(query_table, k=10)  # Change from 15

# Re-run
python3 main.py
```

### Switch to Cloud LLM

```bash
# Add to .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# Edit main.py, line ~17
judge = ConsistencyJudge(use_cloud=True)

# Re-run
python3 main.py
```

### Debug Single Query

```python
# Create debug CSV
echo "id,book_name,char,caption,content" > debug.csv
echo "1,The Count of Monte Cristo,Edmond Dantes,Test,Test backstory" >> debug.csv

# Run
INPUT_DATA=debug.csv python3 main.py

# Check output
cat results.csv
```

## Performance Tips

### Speed Up Embedding (One-Time)
```bash
# First run: 3-5 minutes (embedding)
python3 main.py

# Subsequent runs: ~20 seconds (cached)
# (if books haven't changed)
```

### Speed Up LLM Inference
```bash
# Option 1: Use cloud API (10x faster)
judge = ConsistencyJudge(use_cloud=True)

# Option 2: Reduce k (1.5x faster)
retrieved_results = retriever.retrieve(query_table, k=10)

# Option 3: Use smaller model
ollama pull mistral:7b-instruct-q4_0  # Quantized version
```

## Code Quality

### Linting
```bash
# Format code
black main.py src/

# Check types
mypy main.py
```

### Documentation
```bash
# Generate API docs
pdoc --html src/
```

## Next Steps

1.  ✅ Run validation: `python3 validate_accuracy.py`
2.  ✅ Run final inference: `./run_inference.sh`
3.  ✅ Package submission: `python3 package_submission.py`
4.  ✅ Submit: Upload `epochzero_KDSH_2026.zip`
