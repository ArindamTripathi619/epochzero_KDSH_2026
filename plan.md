You are solving a binary long-context **consistency classification** task over novels + hypothetical backstories, and you must meaningfully use Pathway (and optionally BDH / llm‑app).[1][2][3]

Below is a compact but detailed plan: which track to choose, how to design the system, how to set up the repos, and how to proceed step‑by‑step.

***

## 1. Track choice and overall strategy

Given your background (embedded / systems, but now doing an applied DS hackathon) and the time pressure, **Track A is the better choice**.  

- Track A only requires using Pathway as a framework for ingest, storage, retrieval, or orchestration; you are free to use standard LLMs / classifiers for the core reasoning.[3]
- Track B requires **meaningful BDH modeling** (pretraining/representation experiments etc.), which is more research-y and will cost a lot of time just to get stable; it is rewarded for representation-learning analysis, not for clean engineering.[3]

**Recommendation:**  
- Compete in **Track A**.  
- Architect the system so you *could* plug in BDH representations later (for a small Track B-style extension), but keep the core submission firmly in Track A.

***

## 2. Data understanding and target formulation

From `train.csv` / `test.csv` and the problem statement:[2][1][3]

- Each training row has:
  - `id`  
  - `bookname` (e.g. *In Search of the Castaways*, *The Count of Monte Cristo*)  
  - `char` (character)  
  - `caption` (short section title)  
  - `content` (backstory snippet)  
  - `label` in `{consistent, contradict}` (map to {1,0})  
- Each test row has the same fields **without** `label`.[1]
- The full novel text is provided separately as `.txt` files (you already attached two books; hackathon drive has more).[4][5][3]

The **task**:  
Given `(novel_text, character, backstory_snippet)` → predict whether snippet is globally consistent with the full novel (1) or contradicted by it (0).[2][3]

***

## 3. High-level system design (Track A with Pathway + LLM / classifier)

Design a two-layer system:

1. **Pathway layer (data & orchestration)**  
   - Ingest full novels as documents with metadata.[3]
   - Ingest the backstory snippets (`train.csv`, `test.csv`).[1][2]
   - Maintain a vector store over novel segments and optionally over canonical “fact nodes” extracted from the novels using LLM.[3]
   - Expose a simple API (HTTP or CLI) to compute features / prompts for each `(book, char, content)` row and get a prediction.  

2. **Reasoning / modeling layer**  
   Combine two signals:  

   - **(A) Retrieval + LLM scoring**  
     - For each backstory snippet, query the vector store for top‑k relevant passages from the corresponding novel.  
     - Build a structured prompt that:
       - Lists backstory claims (optionally extracted as bullet points).  
       - Shows retrieved evidence snippets and asks an LLM to judge “consistent vs contradict” and optionally provide a 1–2 line rationale like in the example.[3]
     - Parse the LLM output into a probability / label.  

   - **(B) Supervised classifier on textual features**  
     - For each training sample, create a feature representation:  
       - Concatenate `char + caption + content` and the top‑k retrieved novel passages.  
       - Encode with an encoder (e.g., sentence-transformer, MiniLM, etc.) to get embeddings.  
     - Train a light classifier (Logistic Regression / XGBoost / shallow MLP) on top to predict label {0,1}.[2]
     - Optionally also include simple heuristics (e.g., lexical overlaps, contradictions cues like negations, timeline mismatches).  

   At inference:
   - Run both (A) and (B) and combine:
     - `p_final = α * p_classifier + (1-α) * p_llm`, then threshold.  
   - For the optional Evidence/Rationale column, output the LLM explanation from (A).[3]

This hybrid approach gives:
- **Accuracy & robustness** (classifier)  
- **Evidence‑based explanation** (LLM pipeline, rewarded in Track A)[3]
- Strong use of Pathway for long‑context handling and orchestration, which is explicitly required.[3]

***

## 4. Project setup with Pathway and llm-app

### 4.1 Local environment

Steps:

- Create a new repo `TEAMNAME_KDSH_2026`.  
- Inside, create a Python environment (e.g., `conda` or `venv`) and install:  
  - `pathway`  
  - `pathway-llm-app` (or clone `pathwaycom/llm-app`)  
  - `transformers`, `sentence-transformers` or similar  
  - `scikit-learn` or `xgboost`  
  - `pandas`, `numpy`  

### 4.2 Cloning the required repos

- Clone `https://github.com/pathwaycom/pathway` as a submodule or separate folder.  
- Clone `https://github.com/pathwaycom/llm-app` as another submodule or copy selected templates.  
- The hackathon text mentions “Pathway Framework: Core Engine, LLM App templates, connectors, LLM xPack, vector store docs, LangGraph agents cookbook”; these are your building blocks.[3]

Folder structure suggestion:

- `TEAMNAME_KDSH_2026/`
  - `data/` – novels (`.txt`), `train.csv`, `test.csv`  
  - `notebooks/` – EDA, prototyping  
  - `src/`
    - `pathway_pipeline/` – Pathway app
      - `ingest_novels.py`
      - `ingest_snippets.py`
      - `retrieval.py`
      - `api_server.py`
    - `models/`
      - `embedder.py`
      - `classifier.py`
      - `llm_judge.py`
    - `utils/`
      - `preprocess.py`
      - `prompt_templates.py`
  - `configs/`
    - `pathway_config.toml` / YAML  
  - `results/` – predictions, logs  
  - `report/` – LaTeX/Markdown for your 10‑page report  

***

## 5. Pathway: concrete pipeline design

You must use Pathway “in at least one meaningful part of the system pipeline” for Track A.[3]

### 5.1 Ingest novels into a Pathway table + vector store

- Use Pathway connectors (local folder connector is enough) to read the novel `.txt` files into a table with columns:
  - `book_id`, `bookname`, `segment_id`, `text`, `start_char`, `end_char`.  
- Implement a chunker:
  - e.g., split novels into overlapping windows (e.g., 800–1200 words with 200 overlap) to keep each chunk LLM-friendly but preserve context.  
- Use Pathway’s vector store integration:
  - For each chunk, compute embedding (could be via external encoder / LLM app embedder).
  - Store embeddings and metadata in the Pathway-native vector store.[3]

### 5.2 Ingest backstory snippets (train/test)

- Ingest `train.csv` / `test.csv` as separate tables via CSV connector.[1][2][3]
- Normalise:
  - `label` → `1` for `consistent`, `0` for `contradict` in training.[2]
  - Add `book_id` by mapping `bookname` to novel id.  

### 5.3 Retrieval function inside Pathway

Implement a Pathway UDF / operator:

- Input: `(book_id, char, caption, content)`  
- Process:
  - Build a query text (e.g., `char + caption + content`).  
  - Query the Pathway vector store *filtered by `book_id`* for top‑k chunks.  
- Output: `top_k_chunks` with metadata.  

This retrieval is Pathway’s **meaningful use**: long-context management, indexing, and query over full novels.[3]

### 5.4 Orchestration

Use the llm-app / LangGraph-style templates to define an agent that:

- Given an event `(book_id, char, content)` triggers retrieval;  
- Collects the retrieved text;  
- Calls external LLM for judgment via Pathway’s LLM integration (LLM xPack).[3]
- Optionally logs intermediary reasoning steps.  

This can be exposed as:

- A CLI command (`python -m src.pathway_pipeline.api_server --run train`), or  
- An HTTP endpoint defined in the llm-app template.

***

## 6. Modeling plan (step-by-step)

### 6.1 EDA and simple baseline

From `train.csv` sample you saw:[2]

- Multiple entries per `(bookname, char)` with different `content` bits, some consistent, some contradicting.  
- Good first baseline: treat this as a plain text classification problem on `char + caption + content` **without** novel context:
  - Train a text classifier (e.g., `sentence-transformers` embedding + Logistic Regression).  
  - Evaluate via cross-validation or hold-out to have a sanity check.  

This baseline is your “non‑Pathway” reference; you then show how adding long-context retrieval via Pathway improves.[3]

### 6.2 Features with retrieval

For each training sample:

- Use the Pathway retrieval operator to get top‑k novel chunks (k ≈ 5–10).  
- Construct an extended text:
  - `T = "[BACKSTORY]\n" + content + "\n[CHAR] " + char + "\n[CAPTION] " + caption + "\n[EVIDENCE]\n" + concat(top_k_chunks)`  
- Encode `T` with an encoder model; train a classifier on top.  

Fine‑tune:

- Try both:
  - Using only `content` vs. using `content+evidence`.  
  - Vary k and chunk sizes to see effect on validation accuracy.  

### 6.3 LLM judgment pipeline

Use Pathway’s LLM connectors / llm-app template:

- Prompt structure example:

  - System:  
    - “You are a literary consistency judge. Decide if a proposed backstory is globally consistent with a novel given evidence passages. Answer with JSON {label: 0 or 1, reason: '...'}.”  
  - User:  
    - Book: `<bookname>`  
    - Character: `<char>`  
    - Caption: `<caption>`  
    - Backstory: `<content>`  
    - Evidence from the novel (numbered snippets with location).  

- Ensure you:
  - Include both supportive and potentially conflicting evidence (top-k based on similarity).  
  - Ask the model to reason step‑by‑step internally but output only final JSON.  

Use training data to:

- Run the LLM judge on train rows and see how its raw accuracy compares to supervised classifier.  
- Optionally calibrate by fitting a logistic layer on top of the LLM’s confidence (if accessible) or heuristics (e.g., use logit of label probability).  

### 6.4 Ensembling

- Compute `p_class` from classifier and `p_llm` from LLM.  
- Tune α on a validation split to maximise F1 / accuracy:  
  - `p_final = α p_class + (1-α) p_llm`  
- Threshold at 0.5, or optimise threshold on validation.  

***

## 7. How to proceed step-by-step (practical timeline)

### Phase 1 – Day 1–2: Setup & baseline

- Set up repo, environment, and pull Pathway + llm-app.  
- Load `train.csv` into a notebook, inspect label distribution and simple patterns.[2]
- Implement baseline classifier without novel context; get validation metrics.  

### Phase 2 – Day 2–3: Pathway ingestion & retrieval

- Write Pathway pipeline to:
  - Read novel `.txt` files and chunk them.[5][4]
  - Build vector store with embeddings.  
  - Read `train.csv` / `test.csv` as tables.[1][2]
  - Define retrieval operator (top‑k chunks per snippet).  
- Confirm that for a given row you can quickly see the retrieved paragraphs (for debugging).  

### Phase 3 – Day 3–4: Classifier with context + LLM judge

- Add retrieval-based features and retrain classifier.  
- Set up LLM judge via llm-app:
  - Use a config file to define which model, which endpoint (OpenAI, etc.).  
  - Implement the prompt builder and response parser.  
- Compare:
  - Baseline vs. retrieval‑aware classifier vs. LLM-only vs. ensemble on validation.  

### Phase 4 – Day 4–5: Evidence rationale and polish

- For Track A, Evidence Rationale is optional but strongly encouraged.[3]
  - Use the LLM’s short explanation as the `Rationale` column in `results.csv`.  
  - Make sure each rationale references at least one evidence snippet (e.g., quoting a phrase).  
- Add logging:
  - Save which chunks were retrieved, the LLM decision, classifier decision, final label.  
- Implement error analysis:
  - Inspect misclassified examples: often due to missing evidence or subtle timeline/causal issues.  

### Phase 5 – Final: Packaging and submission

- Add a top‑level script `run.py`:

  - `python run.py --mode train`  
    - Trains classifier, saves model.  
  - `python run.py --mode predict --input data/test.csv --output results.csv`  
    - Starts Pathway pipeline (or uses pre-built index) and outputs predictions and rationales.  

- Ensure a clean environment run:
  - Document dependencies in `requirements.txt`.  
  - Provide a small `README.md` with exact commands to reproduce results end‑to‑end, as required.[3]
- Prepare report (≤10 pages) focusing on:
  - Your **handling of long context** (chunking, retrieval, Pathway usage).[3]
  - How you **distinguish causal signals from noise** (e.g., emphasising events, timelines, and constraints rather than surface similarity).[3]
  - Failure modes and limitations.  

***

## 8. Immediate next steps for you

Given what you already attached:

1. Confirm that `The-Count-of-Monte-Cristo.txt` and `In-search-of-the-castaways.txt` match the `bookname` fields in `train.csv` / `test.csv` using a small script for mapping.[4][5][1][2]
2. Decide on Track A officially and design your repo structure now, so every piece you code fits the final submission requirements.[3]
3. Start with the baseline classifier (no Pathway) today; as soon as that works, move to Pathway ingestion + retrieval.  

If you share what compute and which LLM/API you can use (OpenAI, local models, etc.), a more concrete choice of encoder model, chunk size, and LLM configuration can be sketched specifically for your setup.

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/e3093f8d-ca9e-421a-89a2-ef1187095784/test.csv)
[2](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/fd17fbcf-2206-490f-91b3-10c8a36967fb/train.csv)
[3](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/0853d1df-5065-474e-9f5f-e7067ce03c99/Problem_Statement.md)
[4](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/fc45d67c-8783-4165-baea-258590e02ca8/The-Count-of-Monte-Cristo.txt)
[5](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/86492829/6a8d56cb-b7ab-4e88-a0a2-89d89deafe84/In-search-of-the-castaways.txt)
[6](https://github.com/pathwaycom/pathway)