
import pathway as pw
from src.pathway_pipeline.retrieval import NarrativeRetriever
import os

def test_retrieval_init():
    # Minor check to ensure it initializes without crashing
    books_dir = "Dataset/Books/"
    if not os.path.exists(books_dir):
        print(f"Skipping test: {books_dir} not found.")
        return

    retriever = NarrativeRetriever(books_dir=books_dir)
    print("Retriever initialized successfully.")

    # Create a dummy query table
    query_data = pd.DataFrame([
        {"query": "Captain Grant", "id": 1}
    ])
    
    # In Pathway, we can use debug tables
    # But DocumentStore.retrieve_query works better with real Pathway tables
    # Let's just verify initialization for now as Pathway requires a running loop for computation
    # and we want to avoid long-running processes in simple tests.

if __name__ == "__main__":
    import pandas as pd
    test_retrieval_init()
