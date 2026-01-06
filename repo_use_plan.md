You can treat the two repos as your “engine + app template” stack: **`pathway`** gives you streaming tables + vector index + connectors, and **`llm-app`** gives you ready-made RAG / LLM pipelines you can adapt to this novel/backstory consistency task.[1][2]

***

## 1. Role of `pathway` in your hack

From the problem statement, Track A explicitly wants Pathway used for at least one meaningful part of the pipeline, especially for long-context handling.[2]

Use `pathway` to:

- **Ingest novels and backstories**
  - Read all `.txt` novels (like the two you attached) into a Pathway table with `book_id, segment_id, text, start_offset, end_offset`.[3][4][2]
  - Read `train.csv` and `test.csv` into Pathway tables with columns like `id, bookname, char, caption, content, label`.[5][1][2]
- **Chunk and index the novels**
  - Implement chunking (e.g., 800–1200 words with overlap) in a Pathway transformation, and store each chunk as a row.
  - Use Pathway’s built‑in **vector index** to embed chunks and build a per‑book vector store, exactly in line with their “live document indexing / vector store” examples.[1][2]
- **Retrieval over long novels**
  - Define a Pathway function that, for each backstory row `(bookname, char, content)`, builds a query string and retrieves top‑k chunks from the corresponding book’s index.
  - This uses Pathway as the central retrieval layer: long‑context management is one of the explicit evaluation criteria.[2]
- **Orchestrate the pipeline**
  - Use Pathway tables and streaming logic to connect:
    - Ingest → chunk → embed → index → retrieve → call LLM / classifier → write predictions table, export to CSV `results.csv`.[2]
  - This satisfies the “document store or orchestration layer” requirement for Track A.[2]

In short, `pathway` is your **Core Engine**: dataflow, chunking, embeddings, vector search.

***

## 2. Role of `llm-app` in your hack

The `llm-app` repo gives you ready-made **AI pipelines** (RAG, vector store services, Q&A, etc.) that already integrate embeddings, Pathway tables, and LLM calls.[1]

You can leverage it as follows:

- **Start from the “Live Document Indexing (Vector Store / Retriever)” template**
  - That template already:
    - Reads documents from a file system or drive.
    - Chunks them.
    - Embeds and builds a vector index.
    - Exposes a REST API to query.[1]
  - Adapt it so:
    - Data source is your `novels/` folder instead of PDFs.
    - Documents are plain `.txt` novels.
    - You add metadata like `bookname` so retrieval can filter by book.

- **Adapt a Question‑Answering RAG or Adaptive RAG template**
  - These templates show how to:
    - Receive a request via HTTP.
    - Retrieve relevant chunks from the index.
    - Call an LLM with a structured prompt that includes retrieved text.[1]
  - Instead of answering a free‑form question, modify the logic to:
    - Input: `bookname, char, caption, content`.
    - Use a retriever (from the document index) restricted to `bookname`.
    - Build a **consistency‑judgment prompt** that asks the LLM to return `{label: 0/1, reason: "..."}` based on backstory + evidence.

- **Use the app’s HTTP API as your scoring service**
  - Run the adapted llm-app as a Docker container or local app (as intended by the repo).[1]
  - Write a small script that:
    - Iterates over rows in `train.csv` / `test.csv`.
    - Calls the llm-app HTTP endpoint with `(bookname, char, caption, content)`.
    - Receives `label` and `reason`, and writes them into `results.csv` in the required format.[5][2][1]

In short, `llm-app` is your **application template**: ready infrastructure for a RAG‑like LLM classifier over Pathway’s index.

***

## 3. Concrete integration pattern (minimal but valid)

A simple and still hackathon‑strong pattern is:

1. **Indexing service (llm-app + pathway)**
   - Use “Live Document Indexing (Vector Store / Retriever)” template from `llm-app`.
   - Point it at your novels folder; adapt config so each file is treated as one book, with filename → `bookname`.[1]
   - Confirm that you can send a query `"Kai-Koumou childhood and war"` and retrieve relevant chunks from *In Search of the Castaways*.[4][2]

2. **Consistency-judger endpoint**
   - Add a new endpoint to the llm-app:
     - Request JSON:
       - `bookname`, `character`, `caption`, `backstory_text`.
     - Logic:
       - Construct query: `character + caption + backstory_text`.
       - Call the vector retriever with `bookname` filter to get top‑k passages.
       - Build a prompt describing:
         - Backstory claims.
         - Evidence passages with IDs/locations.
         - Task: output `{"label": 1 or 0, "reason": "1–2 line explanation referencing evidence passages"}`.
       - Call LLM and return its parsed JSON.

3. **Offline scoring script**
   - Separate Python script (can also be run inside Pathway) that:
     - Reads `train.csv` and `test.csv`.[5][1]
     - Calls the endpoint for each row in `test.csv`.
     - Writes `results.csv` with columns `Story ID, Prediction, Rationale`, matching the example format.[2]
   - For training / validation, you can also:
     - Call the endpoint on `train.csv` and compare with ground‑truth labels (`consistent` / `contradict` → 1/0) to tune your prompt or retrieval parameters.[5][2]

This already uses both repos as requested: `pathway` for indexing/retrieval and `llm-app` as your LLM‑based decision app.

***

## 4. Slightly more advanced use (if you have time)

If you want to go beyond a pure LLM judge:

- Use Pathway to **export retrieved evidence** for each training row as features, then train a light classifier (e.g., sentence‑transformer embeddings + Logistic Regression) in a normal Python script.[5][2]
- Use llm-app only for:
  - Evidence selection (retriever).
  - Optional explanation generation (rationale text).
- Combine classifier probability and LLM probability into an ensemble.

This keeps the heavy lifting (long-context handling) in Pathway / llm-app while letting you do classic ML where you are more comfortable.[2]

***

## 5. What to implement first

1. Clone **both repos** and run a small llm-app example (e.g., Question‑Answering RAG or Live Document Indexing) on a toy folder, to understand the config and how the HTTP API looks.[1]
2. Replace the example documents with your two novels and verify that retrieval works.[3][4]
3. Add the consistency‑judger endpoint and a simple offline script that calls it for each row and outputs `results.csv` in the required format.[5][2][1]

Once this basic path is running end‑to‑end, further improvements (better chunking, better prompts, classifier + ensemble) can be added without changing the overall architecture.

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/e3093f8d-ca9e-421a-89a2-ef1187095784/test.csv)
[2](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/0853d1df-5065-474e-9f5f-e7067ce03c99/Problem_Statement.md)
[3](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/fc45d67c-8783-4165-baea-258590e02ca8/The-Count-of-Monte-Cristo.txt)
[4](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/6a8d56cb-b7ab-4e88-a0a2-89d89deafe84/In-search-of-the-castaways.txt)
[5](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/fd17fbcf-2206-490f-91b3-10c8a36967fb/train.csv)
[6](https://github.com/pathwaycom/pathway)