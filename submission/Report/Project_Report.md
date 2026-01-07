# KDSH 2026 Project Report (Track A)

## Overall Approach
Our system implements a Retrieval-Augmented Generation (RAG) pipeline designed to verify the consistency of character backstories against long-form novels. We chose Track A to leverage Pathway's streaming prowess for efficient document ingestion and vector retrieval, coupled with an LLM judge for reasoning.

### Architecture
1.  **Ingestion & Indexing**: We use Pathway to ingest full text novels. A custom regex-based splitter identifies chapters and sections (e.g., "CHAPTER I", "Part II"), ensuring that every text chunk preserves its temporal context (Chapter number, Progress %).
2.  **Retrieval**: We use `SentenceTransformer` (all-MiniLM-L6-v2) to embed chunks. For each query (backstory claim), we retrieve the top `k=15` most relevant chunks.
3.  **Filtering**: Post-retrieval, we strictly filter chunks to ensure evidence comes only from the target book.
4.  **Reasoning**: A "Judge" LLM (Mistral/Claude) analyzes the retrieved evidence against the backstory using a "Dossier" format prompt, effectively distinguishing between explicit contradictions and mere silence.

## Handling Long Context & Temporal Strategy
- **Chapter-Aware Chunking**: Instead of arbitrary sliding windows, we respect narrative boundaries. Our regex `(?m)^(?:CHAPTER|Chapter|PART|Part|BOOK|Book)\s+(?:[IVXLCDM\d]+|[A-Z]+).*$` captures structural units.
- **Progress Tracking**: We calculate a `progress_pct` for each chunk. The LLM is instructed to use this metadata to detect temporal anachronisms (e.g., childhood backstory contradicted by Chapter 1 adult actions).
- **Deep Retrieval**: We increased retrieval depth (`k=15`) to mitigate "No evidence found" errors, ensuring broad coverage of the narrative.

## Causal Reasoning & Noise Distinction
- **"Silence != Contradiction"**: Our core principle. We explicitly instruct the model that absence of evidence is not evidence of absence.
- **Dossier Rationale**: We enforce a strict output format: `EVIDENCE -> CLAIM -> ANALYSIS`. This forces the model to ground every decision in specific text segments, reducing hallucination and noise.

## Architectural References (Pathway llm-app)
We drew significant inspiration from Pathway's `llm-app` templates:
- **Live Document Indexing**: Referenced for setting up the real-time vector store and file watchers.
- **Question Answering RAG**: Provided the blueprint for the retrieval-generation loop and schema definitions.

## Failure Case Analysis & Limitations
- **Ambiguity in Silence**: In 5-10% of cases, the distinction between "implausible" and "contradictory" is subjective. Our model tends to lean towards "Consistent" when in doubt (Consumer-safe approach).
- **Complex Multi-Hop Reasoning**: Implicit contradictions that require connecting three distant facts (Chapter 1 + Chapter 20 -> implies X, but Backstory says Y) remain challenging for standard RAG without an iterative agentic loop.
- **Retrieval Gaps**: While we improved `k`, extremely obscure minor character details mentioned once in 100k words may still be missed.
