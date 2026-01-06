
import os
import pathway as pw
import pandas as pd
from src.pathway_pipeline.retrieval import NarrativeRetriever
from src.models.llm_judge import ConsistencyJudge

# Constants
BOOKS_DIR = "Dataset/Books/"
TRAIN_DATA = "Dataset/train.csv"
OUTPUT_FILE = "results.csv"

def main():
    # 1. Initialize Components
    retriever = NarrativeRetriever(books_dir=BOOKS_DIR)
    judge = ConsistencyJudge(use_cloud=False) # Default to local Ollama

    # 2. Load Queries
    # In a real Pathway app, we might use pw.io.csv.read
    # For a hackathon batch process, we can ingest the CSV
    queries = pw.io.csv.read(
        TRAIN_DATA,
        schema=None, # Auto-detect schema
        mode="static"
    )

    # 3. Preparation: Build retrieval queries
    # DocumentStore expects a 'query' column.
    # Advanced: use metadata_filter to narrow search to the specific book.
    # The 'book_name' in train.csv needs to be mapped to the file path or a metadata field.
    # pathway.io.fs.read puts the file name in metadata['path'].
    
    query_table = queries.select(
        query=pw.this.character + " " + pw.this.content,
        id=pw.this.id,
        character=pw.this.character,
        backstory=pw.this.content,
        book_name=pw.this.book_name,
        # DocumentStore.retrieve_query expects metadata_filter as a boolean expression or string
        # For simplicity, if we indexed with metadata, we can filter by path.
        # We need to map book_name to the expected path substring.
        metadata_filter=pw.this.book_name.apply(lambda book_name: f"path LIKE '%{book_name}%'")
    )

    # 4. Retrieval
    # retrieve_query returns a table with original columns + retrieved chunks
    # Note: Custom metadata filtering might be needed here.
    retrieved_results = retriever.retrieve(query_table, k=3)

    # retrieved_results has 'result' column which is a list of chunks
    # Let's join them into a single evidence string.
    @pw.udf
    def combine_evidence(chunks: list) -> str:
        return "\n---\n".join([c['text'] for c in chunks])

    evidence_table = retrieved_results.select(
        *pw.this,
        evidence=combine_evidence(pw.this.result)
    )

    # 5. Consistency Judgment
    # Build prompt
    prompt_table = evidence_table.select(
        *pw.this,
        prompt=judge.build_consistency_prompt(
            backstory=pw.this.backstory,
            character=pw.this.character,
            evidence=pw.this.evidence
        )
    )

    # Run LLM
    final_results = judge.judge(prompt_table)

    # 6. Post-processing & Output
    # The 'result' from judge.judge is the LLM raw string.
    # We should parse JSON.
    @pw.udf
    def parse_label(llm_output: str) -> int:
        try:
            # Try to find JSON block if LLM added fluff
            if "```json" in llm_output:
                llm_output = llm_output.split("```json")[1].split("```")[0]
            data = json.loads(llm_output)
            return int(data.get("label", 0))
        except:
            return 0 # Default to contradicted if parse fails

    output_table = final_results.select(
        id=pw.this.id,
        label=parse_label(pw.this.result)
    )

    # Export to CSV
    pw.io.csv.write(output_table, OUTPUT_FILE)

    # Pathway runs everything as a compute graph
    pw.run()

if __name__ == "__main__":
    main()
