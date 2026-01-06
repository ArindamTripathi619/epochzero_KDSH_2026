import os
import json
import pathway as pw
import pandas as pd
from src.pathway_pipeline.retrieval import NarrativeRetriever
from src.models.llm_judge import ConsistencyJudge, build_consistency_prompt

# Constants
BOOKS_DIR = "Dataset/Books/"
TRAIN_DATA = "Dataset/train.csv"
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
        label: str

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
    # retrieve_query returns a table with original columns + retrieved chunks
    # Note: Custom metadata filtering might be needed here.
    retrieved_results = retriever.retrieve(query_table, k=3)

    # retrieved_results has 'result' column which is a list of chunks
    # Let's join them into a single evidence string.
    @pw.udf
    def combine_evidence(chunks: list) -> str:
        if not chunks:
            return "No evidence found."
        return "\n---\n".join([str(c) for c in chunks])

    evidence_table = retrieved_results.select(
        *pw.this,
        evidence=combine_evidence(pw.this.retrieved_chunks)
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
        query_id=pw.this.query_id,
        label=pw.apply(lambda l: "consistent" if l == 1 else "contradict", parse_label(pw.this.result)),
        rationale=parse_rationale(pw.this.result)
    )

    # Export to CSV
    pw.io.csv.write(output_table, OUTPUT_FILE)

    # Pathway runs everything as a compute graph
    pw.run()

if __name__ == "__main__":
    main()
