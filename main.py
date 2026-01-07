import os
import json
import pathway as pw
import pandas as pd
from src.pathway_pipeline.retrieval import NarrativeRetriever
from src.models.llm_judge import ConsistencyJudge, build_consistency_prompt

# Constants
BOOKS_DIR = "Dataset/Books/"
TRAIN_DATA = os.getenv("INPUT_DATA", "Dataset/test.csv")
OUTPUT_FILE = "results.csv"

def main():
    # 1. Initialize Components
    retriever = NarrativeRetriever(books_dir=BOOKS_DIR)
    # Fallback to local Ollama (Mistral)
    judge = ConsistencyJudge(use_cloud=False, model_name="mistral")

    # 2. Load Queries
    # Define schema from the CSV file
    class QuerySchema(pw.Schema):
        id: int
        book_name: str
        char: str
        caption: str
        content: str

    queries = pw.io.csv.read(
        TRAIN_DATA,
        schema=QuerySchema,
        mode="static"
    )

    # 3. Preparation: Build retrieval queries
    # DocumentStore expects a 'query' column.
    # Advanced: use metadata_filter to narrow search to the specific book.
    # The 'book_name' in train.csv needs to be mapped to the file path or a metadata field.
    # pathway.io.fs.read puts the file name in metadata['path'].
    
    query_table = queries.select(
        query=pw.this["char"] + " " + pw.this["content"],
        query_id=pw.this["id"],
        character=pw.this["char"],
        backstory=pw.this["content"],
        book_name=pw.this["book_name"],
        # Use string concatenation to avoid ANY type from UDF
        metadata_filter="contains(path, '" + pw.this["book_name"] + "')"
    )
    
    # Handle the 'In Search of the Castaways' capitalization fix using another select if needed, 
    # but let's try the simple version first.

    # 4. Retrieval
    # retrieve_query returns a table with original columns + retrieved chunks + metadata
    # Note: Custom metadata filtering might be needed here.
    retrieved_results = retriever.retrieve(query_table, k=15)

    # retrieved_results has 'result' column which is a list of chunks
    # Let's join them into a single evidence string.
    # NOTE: We now do book filtering HERE since metadata_filter was removed from retrieval
    @pw.udf
    def combine_evidence(chunks: list, metadata: list, target_book: str) -> str:
        """
        Combines retrieved chunks into formatted evidence string.
        Filters chunks to only include those from the target book.
        """
        if not chunks:
            return "No evidence found."
        
        formatted_evidence = []
        # Handle cases where metadata might be missing or length mismatch
        for i, chunk in enumerate(chunks):
            # Pathway returns metadata as Json objects, need to convert to dict
            meta = metadata[i] if i < len(metadata) else {}
            
            # Convert Pathway Json object to Python dict
            if hasattr(meta, 'as_dict'):
                meta = meta.as_dict()
            elif hasattr(meta, 'to_dict'):
                meta = meta.to_dict()
            elif not isinstance(meta, dict):
                # Fallback: try to convert it to dict somehow
                try:
                    meta = dict(meta)
                except:
                    meta = {}
            
            # BOOK FILTERING: Check if this chunk is from the target book
            chunk_path = str(meta.get("path", "")).lower()
            source_file = str(meta.get("source_file", "")).lower()
            target_book_lower = target_book.lower()
            
            # Match if target book name appears in either path or source_file (case-insensitive)
            # Handle both "The Count of Monte Cristo" and "In Search of the Castaways"
            if target_book_lower not in chunk_path and target_book_lower not in source_file:
                continue  # Skip chunks from other books
            
            chapter = meta.get("chapter", "Unknown Chapter")
            progress = meta.get("progress_pct", "?")
            
            # Format: [SOURCE: Chapter 1 | 14%] Content...
            entry = f"[{chapter} | {progress}%]\n{str(chunk)}"
            formatted_evidence.append(entry)
        
        if not formatted_evidence:
            return f"No evidence found from '{target_book}'."
            
        return "\n---\n".join(formatted_evidence)

    evidence_table = retrieved_results.select(
        *pw.this,
        evidence=combine_evidence(pw.this.retrieved_chunks, pw.this.retrieved_metadata, pw.this.book_name)
    )

    # 5. Consistency Judgment
    # Build prompt
    prompt_table = evidence_table.select(
        *pw.this,
        prompt=build_consistency_prompt(
            backstory=pw.this.backstory,
            character=pw.this.character,
            evidence=pw.this.evidence
        )
    )

    # Run LLM
    # 6. Judicial Reasoning
    final_results = judge.judge(prompt_table)

    # 7. Output Generation
    # The 'result' from judge.judge is the LLM raw string.
    # We should parse JSON.
    @pw.udf
    def parse_label(result_js: str) -> int:
        try:
            if "```json" in result_js:
                result_js = result_js.split("```json")[1].split("```")[0]
            data = json.loads(result_js)
            return int(data.get("label", 0))
        except:
            return 0

    @pw.udf
    def parse_rationale(result_js: str) -> str:
        try:
            if "```json" in result_js:
                result_js = result_js.split("```json")[1].split("```")[0]
            data = json.loads(result_js)
            return str(data.get("rationale", "No rationale provided"))
        except:
            return "Parsing error"
 
    output_table = final_results.select(
        **{"Story ID": pw.this.query_id},
        Prediction=parse_label(pw.this.result),
        Rationale=parse_rationale(pw.this.result)
    )

    # Export to CSV
    pw.io.csv.write(output_table, OUTPUT_FILE)

    # Pathway runs everything as a compute graph
    pw.run()
    
    # Post-processing: Clean up Pathway's internal columns (time, diff)
    # This ensures the final CSV matches the submission format exactly
    try:
        df = pd.read_csv(OUTPUT_FILE)
        # Keep only the required columns
        required_cols = ["Story ID", "Prediction", "Rationale"]
        df = df[required_cols]
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"[INFO] Cleaned CSV output: {len(df)} predictions written to {OUTPUT_FILE}")
    except Exception as e:
        print(f"[WARNING] Could not clean CSV: {e}")

if __name__ == "__main__":
    main()
