# KDSH 2026 - Track A: Narrative Consistency Classification
## Team: epochzero

---

## 1. Summary and Motivation

### Motivation
In the realm of long-form literature, maintaining narrative consistency is a monumental task. As characters evolve across hundreds of chapters, authors and editors often face the risk of subtle contradictions in backstory, causal logic, or temporal progression. The **Kharagpur Data Science Hackathon (KDSH)** challenge for Track A specifically tasks us with automating this consistency check using a system that can reason across vast amounts of text (novels) to validate hypothetical character backstories.

### Our Solution
We have built a **Retrieval-Augmented Generation (RAG)** pipeline designed for extreme scale and logical precision. Our system does not just "predict" a label; it constructs a **Dossier-style Rationale** that cites specific evidence from the source text, ensuring every decision is grounded in textual fact.

---

## 2. Details of Work Implementation

### Architecture Overview
Our system is built on three main pillars:
1.  **Pathway Framework**: Used for high-speed document ingestion, vector indexing, and orchestration of the RAG flow.
2.  **Chapter-Aware Retrieval**: Instead of treating a book as a flat string, we split it along chapter boundaries to preserve narrative hierarchy and calculate "temporal progress" (e.g., Chapter 5 of 10 = 50% through the book).
3.  **Local LLM (Mistral)**: We leverage a local Mistral 7B model via Ollama to ensure data privacy, zero API costs, and reproducible reasoning.

### Key Components
- **NarrativeRetriever**: Manages a vector store of the novels. It uses `SentenceTransformers` (`all-MiniLM-L6-v2`) to embed chunks and a `BruteForceKnn` index for exact retrieval. For each query, it fetches the **top 15 most relevant chunks**.
- **Similarity Filtering**: To avoid "cross-contamination" between books, we dynamically filter retrieved evidence to ensure it only comes from the novel mentioned in the character's backstory.
- **Dossier Prompting**: We use a specialized prompt that forces the LLM into a structured chain-of-thought:
  - **EVIDENCE**: What did the book say? (With Chapter/Progress tags)
  - **CLAIM**: What did the backstory claim?
  - **ANALYSIS**: Why is this consistent or contradictory?

---

## 3. Evaluation Analysis

### Validation Methodology
We validated our system using the `train.csv` dataset (80 examples). The system correctly identified **62.5%** of the labels accurately. 

### Quantitative Results
- **Accuracy**: 62.5%
- **Throughput**: ~3.4 queries per minute on standard CPU hardware.
- **Inference Time**: ~20-25 minutes for a full set of 60-80 queries.

### Qualitative Success: The "Dossier" Rationale
Our rationales successfully bridge the gap between "black-box" predictions and human-readable evidence. 
Example from `results.csv`:
> `EVIDENCE: [Chapter 12 | 14%] "Edmond remained in the dungeon..." -> CLAIM: Backstory says he was in London in 1820. -> ANALYSIS: This contradicts the text which establishes he was imprisoned during this period.`

---

## 4. Key Limitations and Failure Cases

### The "Silence != Contradiction" Challenge
A primary failure case (false positives for consistency) occurs when the system cannot find explicit evidence to disprove a claim. We adopted a **conservative heuristic**: unless a direct textual contradiction is found, the system defaults to "Consistent." This prevents the model from "hallucinating" contradictions, which is highly preferred in Track A's "evidence-grounded" criteria.

### Hardware Bottlenecks
- **CPU-Bound Embeddings**: Without a dedicated GPU, initial book ingestion takes 3-5 minutes.
- **Local LLM Latency**: Running 7B models on CPU limits throughput. While cloud APIs are 10x faster, the local approach was chosen for its total privacy and zero cost.

---

## 5. Technical Hardships and Overcoming Obstacles

### The "Pathway ID Pointer" Problem
During development, we discovered that Pathway's framework automatically hijacks any column named `id` and converts it into an internal alphanumeric pointer (e.g., `^TRKZX...`). This rendered our `results.csv` unmatchable to the ground truth.
**Solution**: We implemented a pre-processing hack in `main.py` that renames the column to `story_id_numeric` before ingestion, ensuring that the final output preserves the original numeric IDs required by the hackathon.

---

## 6. Zero-Shot Generalization
Our pipeline is 100% data-agnostic. It does not contain hardcoded rules for any specific novel. By dropping any `.txt` file into the `Dataset/Books` folder, the system automatically:
1. Detects the chapter structure.
2. Builds a vector index.
3. Becomes ready to classify backstories for that NEW text immediately.

---

**Submitted by Team epochzero**  
**KDSH 2026 | Track A**
