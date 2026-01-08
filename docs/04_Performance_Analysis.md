# Performance Analysis and Optimization

## Runtime Breakdown

### Full Pipeline Execution (80 queries on train.csv)

| Phase | Duration | % of Total | Bottleneck |
|-------|----------|------------|------------|
| **Embedding** | 2-5 min | 10-20% | CPU-bound `sentence-transformers` |
| **LLM Inference** | 15-20 min | 80-90% | Local Mistral via Ollama |
| **Post-processing** | <10 sec | <1% | Pandas CSV cleanup |
| **Total** | ~20-25 min | 100% | LLM Inference |

### Per-Query Breakdown (Single Query)

| Step | Duration | Notes |
|------|----------|-------|
| Query preparation | <1ms | Pathway table select |
| Retrieval (k=15) | 50-100ms | Vector similarity search |
| Evidence formatting | 10-20ms | UDF execution |
| LLM inference | 10-20s | **Dominant cost** |
| JSON parsing | <10ms | Extract label/rationale |

**Conclusion**: LLM inference accounts for **99%** of per-query time.

## Bottleneck #1: Embedding Phase

### Symptoms
- Progress bar shows "Batches: 100%" but appears frozen
- CPU usage spikes to 400-600%
- No visible output for 2-5 minutes

### Root Cause

`sentence-transformers` is embedding the entire book library:
```python
# retrieval.py
self.embedder = SentenceTransformerEmbedder(model="all-MiniLM-L6-v2")
```

**Workload**:
- 2 novels × 100k words each = 200k words
- Chunked into ~2,000 segments (200-600 tokens each)
- Each segment → 384-dimensional vector
- **All on CPU** (no CUDA available)

### Profiling Data

```bash
# During embedding phase
$ ps aux | grep python
USER       PID  %CPU  %MEM  COMMAND
DevCrewX  1234  593.2  2.1  python3 main.py
```

**593% CPU** = Using all 6 cores at maximum capacity.

### Why Not GPU?

Our system doesn't have a dedicated NVIDIA GPU:
```bash
$ nvidia-smi
# Command not found
```

**Impact**: CPU embedding is ~10x slower than GPU.

### Optimization Strategies

| Strategy | Speedup | Trade-off |
|----------|---------|-----------|
| Cache embeddings | ✅ 100% (after first run) | Requires disk space |
| Use smaller model | ✅ 2x faster | ❌ Lower retrieval quality |
| GPU acceleration | ✅ 10x faster | ❌ Requires hardware |
| Reduce chunk count | ✅ Linear speedup | ❌ Loses granularity |

**Implemented**: None (embedding time is acceptable for one-time cost).

## Bottleneck #2: LLM Inference

### Symptoms
- Each query takes 10-20 seconds
- 80 queries × 15s = **20 minutes**
- `ollama runner` process consumes 600-800% CPU

### Root Cause

We're running **Mistral 7B** locally via Ollama:
```python
# llm_judge.py
response = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "mistral", "prompt": prompt}
)
```

**Workload per query**:
- Prompt size: 3,000-5,000 words (15 retrieved chunks)
- Token count: ~4,000-6,000 tokens
- Model size: 7 billion parameters
- Hardware: CPU (no GPU offloading)

### Profiling Data

```bash
$ ps aux | grep ollama
USER       PID  %CPU  %MEM  COMMAND
ollama   3189472  787  15.4  /usr/local/bin/ollama runner
```

**787% CPU** = Maxing out all cores.

**Per-token latency**: ~50-100ms on CPU vs. ~5-10ms on GPU.

### Why Local LLM?

**Advantages**:
- ✅ **Zero cost**: No API fees
- ✅ **Privacy**: Data never leaves the machine
- ✅ **Reproducibility**: Consistent results across runs
- ✅ **Offline**: No internet dependency

**Disadvantages**:
- ❌ **Slow**: 10-20s per query vs. 1-2s for cloud APIs
- ❌ **Hardware-bound**: Performance limited by CPU

### Cloud API Comparison

| Provider | Model | Latency | Cost (80 queries) |
|----------|-------|---------|-------------------|
| **Local (Ollama)** | Mistral 7B | 15s/query | $0 |
| OpenAI | GPT-4 Turbo | 2s/query | ~$2.40 |
| Anthropic | Claude 3.5 Sonnet | 1.5s/query | ~$3.20 |
| Google | Gemini 1.5 Pro | 1s/query | ~$1.60 |

**Trade-off**: 10x faster for ~$2-3.

### Optimization Strategies

| Strategy | Speedup | Trade-off |
|----------|---------|-----------|
| Use cloud API | ✅ 10x | ❌ Costs money |
| Smaller model (Mistral 3B) | ✅ 2x | ❌ Lower reasoning quality |
| Reduce k (fewer chunks) | ✅ 1.5x | ❌ Misses evidence |
| Batch processing | ❌ Not supported | Pathway processes sequentially |
| GPU offloading | ✅ 5-10x | ❌ Requires hardware |

**Implemented**: None (local LLM is a design choice for Track A).

## Bottleneck #3: Pathway Overhead

### Symptoms
- Simple operations (select, UDF) feel slower than raw pandas
- Progress dashboard updates consume resources

### Root Cause

Pathway is designed for **streaming data**, not batch processing:
- Maintains a computation graph
- Tracks dependencies for incremental updates
- Logs all operations for debugging

**Overhead**: ~10-20% compared to pure pandas.

### Why Use Pathway?

**Track A Requirement**:
> "All Track A submissions must use Pathway's Python framework in at least one meaningful part of the system pipeline."

**Our Usage**:
- ✅ Document ingestion (`pw.io.fs.read`)
- ✅ Vector store (`DocumentStore`)
- ✅ Retrieval (`query_as_of_now`)
- ✅ Data transformations (UDFs, select, flatten)

**Verdict**: Overhead is acceptable for compliance.

## Performance Optimization Roadmap

### Immediate (No Code Changes)
1.  **Cache Embeddings**: Run once, reuse for multiple experiments
2.  **Reduce Test Set**: Use 10-query subset for rapid iteration
3.  **Profile Logging**: Disable Pathway dashboard for slight speedup

### Short-term (Minor Code Changes)
1.  **Adaptive k**: Use k=5 for short backstories, k=15 for long ones
2.  **Parallel LLM Calls**: If using cloud API, batch requests
3.  **Smaller Chunks**: Reduce max_tokens from 600 to 400

### Long-term (Infrastructure Changes)
1.  **GPU Acceleration**: Use CUDA for embeddings (10x speedup)
2.  **Cloud LLM**: Switch to GPT-4 for 10x faster inference
3.  **Distributed Processing**: Run multiple Ollama instances

## Benchmark Results

### Test Configuration
- **Hardware**: 6-core CPU, 16GB RAM, no GPU
- **Dataset**: 80 queries from `train.csv`
- **Model**: Mistral 7B via Ollama
- **Retrieval**: k=15

### Results

| Metric | Value |
|--------|-------|
| **Total Runtime** | 23 minutes 14 seconds |
| **Embedding Time** | 3 minutes 42 seconds |
| **LLM Inference Time** | 19 minutes 28 seconds |
| **Post-processing** | 4 seconds |
| **Throughput** | 3.4 queries/minute |
| **Avg. Query Latency** | 17.6 seconds |

### Comparison to Baseline

| Configuration | Runtime | Speedup |
|---------------|---------|---------|
| **Our Setup** (CPU + Local LLM) | 23 min | 1x |
| Cloud LLM (GPT-4) | ~3 min | 7.7x |
| GPU + Local LLM | ~8 min | 2.9x |
| GPU + Cloud LLM | ~2 min | 11.5x |

## Recommendations

### For This Hackathon
- ✅ **Keep local LLM**: Meets Track A spirit (self-contained system)
- ✅ **Accept 20-min runtime**: Reasonable for 80 queries
- ✅ **Focus on accuracy**: Performance is secondary to correctness

### For Production Deployment
- 🔄 **Switch to cloud LLM**: 10x faster, minimal cost
- 🔄 **Add GPU**: Essential for real-time inference
- 🔄 **Implement caching**: Avoid re-embedding unchanged books

## Conclusion

Our system's performance is **bottlenecked by local LLM inference**, which is an intentional design choice for:
1.  **Cost-effectiveness** (zero API fees)
2.  **Data privacy** (no external calls)
3.  **Reproducibility** (consistent results)

For a hackathon submission, **20-minute runtime for 80 queries is acceptable**. The architecture is sound, and the bottleneck can be easily resolved with infrastructure upgrades (GPU, cloud API) if needed for production.
