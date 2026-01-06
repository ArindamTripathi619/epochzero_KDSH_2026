
import pathway as pw
import pandas as pd
import os
from typing import List

# Book name to file mapping
BOOK_MAP = {
    "In Search of the Castaways": "In search of the castaways.txt",
    "The Count of Monte Cristo": "The Count of Monte Cristo.txt"
}

def load_backstories(csv_path: str):
    """Loads CSV data into a Pathway table."""
    return pw.io.csv.read(
        csv_path,
        schema=pw.schema_from_dict({
            "id": pw.Type.INT,
            "book_name": pw.Type.STR,
            "char": pw.Type.STR,
            "caption": pw.Type.STR,
            "content": pw.Type.STR,
            "label": pw.Type.STR
        }),
        mode="static"
    )

def load_novels(books_dir: str):
    """
    Loads all novels in the books_dir.
    Each file is a separate novel.
    """
    # Using Pathway's plaintext connector
    return pw.io.plaintext.read(
        books_dir,
        mode="static",
        with_metadata=True
    )

def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """Basic sliding window chunker."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks

if __name__ == "__main__":
    print("Pathway Ingestion module ready.")
