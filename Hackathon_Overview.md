# KDSH 2026: Hackathon Project Overview & Strategy

## 1. Executive Summary & Goal
**Objective**: Build an AI system that acts as a "Consistency Judge" for long-form narratives.
**Core Task**: Given a **Character**, a **Hypothetical Backstory**, and a massive **Novel** (context), determine if the backstory is causally and logically *Consistent* or *Contradictory* with the established events in the book.

**The "Wanted" Output**:
For each test case, we must output:
1.  **Prediction**: `1` (Consistent) or `0` (Contradict).
2.  **Rationale**: A "Dossier-style" evidence trail linking specific book excerpts to backstory claims.

---

## 2. Provided Materials & "Zeroing In" on Data
We have been given three key components. Here is exactly what they are and how we use them:

### A. The Source of Truth (Books)
*Location*: `Dataset/Books/`
*Files*:
*   `In search of the castaways.txt` (~844KB)
*   `The Count of Monte Cristo.txt` (~2.7MB)
*   **Usage**: These are the "Knowledge Bases". We **ingest** these entire text files into our Vector Store.
*   **Challenge**: These are massive (100k+ words). We cannot feed the whole book into an LLM. We must use **Retrieval Augmented Generation (RAG)** to find only the relevant paragraphs.

### B. The Training Data
*Location*: `Dataset/train.csv` (81 rows)
*   **Columns**: `id`, `book_name`, `char`, `caption`, `content` (the backstory), `label` (consistent/contradict).
*   **Usage**: This is our **Validation Set**. Since the hackathon didn't provide a separate validation file, we use `train.csv` to:
    1.  Test if our retrieval logic finds the right evidence.
    2.  Check if our LLM agrees with the gold-standard `label`.
    3.  Tune our prompt strategies (e.g., teaching the model that "Silence is NOT Contradiction").

### C. The Test Data (Submission Target)
*Location*: `Dataset/test.csv` (61 rows)
*   **Columns**: Same as train, but **NO LABEL**.
*   **Usage**: This is the input for our final examination.
*   **Action**: We run our pipeline on this file. It generates `results.csv`, which we zip and submit.

---

## 3. Our Strategy & Approach (Track A)
We are competing in **Track A (Systems Reasoning)**, which focuses on engineering a robust, evidence-based pipeline using `Pathway`.

### The Architecture: "The Judicial RAG"
We treat this as a legal trial. The Backstory is the "Testimony," and the Book is the "Record".

#### Step 1: Ingestion & Temporal Indexing
*   **What we do**: We don't just chop the book into random pieces. We use a **Regex Splitter** to cut the book by **Chapters** (e.g., "CHAPTER I", "Part II").
*   **Why**: Reasoning often depends on *time*. If a backstory says "He lost his arm at age 10," but Chapter 1 says "He waved with both hands," that's a contradiction. We capture `Chapter` and `Progress %` metadata to help the LLM spot these timeline errors.

#### Step 2: Strict Evidence Retrieval
*   **What we do**: When a query comes in for "Captain Nemo" in "The Mysterious Island", we filter our vector search to **only look at that specific book**.
*   **Refinement**: We retrieve the top **15 chunks** (k=15). Why so many? Because often the "smoking gun" evidence is buried in a minor conversation 500 pages in. Standard RAG (k=3) fails here.

#### Step 3: The LLM Judge (Reasoning)
*   **Model**: Mistral (Local w/ Ollama) or Claude (Cloud).
*   **The Prompt**: We act as a "Senior Editor". We strictly instruct the model:
    *   *Silence != Contradiction*: If the book doesn't mention his childhood, and the backstory adds a childhood detail, that is **Consistent**.
    *   *Explicit Contradiction Only*: Only flag it if the text actively refutes the claim.
    *   *Output Format*: `EVIDENCE -> CLAIM -> ANALYSIS`.

---

## 4. Current Status & Implementation
We have built the entire pipeline in `main.py`:
1.  **Orchestration**: `Pathway` handles the data flow.
2.  **Vector Store**: `SentenceTransformers` embeddings.
3.  **Judgement**: `Ollama` connected locally.

**Verification**:
*   We verified the "Chapter Regex" works (Unit Tests Passed).
*   We cleaned up the dependencies (`requirements.txt`).
*   We are currently running the **Full Inference** on `test.csv` to generate our final submission.

## 5. Next Actions
1.  **Wait for Inference**: The local LLM is processing the 61 test cases.
2.  **Package**: Zip `src/`, `main.py`, `results.csv`, and `Report.md`.
3.  **Submit**: Upload `TEAMNAME_KDSH_2026.zip`.
