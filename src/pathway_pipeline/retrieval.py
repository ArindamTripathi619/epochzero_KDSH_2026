import os
import pathway as pw
from typing import Optional
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.xpacks.llm.embedders import SentenceTransformerEmbedder
from pathway.xpacks.llm.parsers import ParseUtf8
from pathway.xpacks.llm.splitters import TokenCountSplitter


class NarrativeRetriever:
    def __init__(self, books_dir: str, embedder_model: str = "all-MiniLM-L6-v2"):
        self.books_dir = books_dir
        
        # 1. Ingest novels
        # Pathway's fs.read handles local directory ingestion
        documents = pw.io.fs.read(
            self.books_dir,
            format="binary",
            with_metadata=True,
            mode="static"
        )
        
        # 2. Setup Indexing Components
        # Using a reliable local embedder
        self.embedder = SentenceTransformerEmbedder(model=embedder_model)
        
        self.retriever_factory = BruteForceKnnFactory(
            embedder=self.embedder,
        )
        
        # Splitter to keep context manageable for LLM
        self.text_splitter = TokenCountSplitter(
            min_tokens=200,
            max_tokens=600,
            encoding_name="cl100k_base"
        )
        
        # Parser for plain text novels
        self.parser = ParseUtf8()
        
        # 3. Create Document Store
        self.store = DocumentStore(
            docs=documents,
            retriever_factory=self.retriever_factory,
            parser=self.parser,
            splitter=self.text_splitter,
        )

    def retrieve(self, queries_table: pw.Table, k: int = 5):
        """
        Retrieves relevant book chunks using lower-level query_as_of_now.
        This bypasses DocumentStore's strict schema check and avoids NotImplementedError.
        """
        index = self.store._retriever
        
        # We MUST select from the JoinResult returned by query_as_of_now 
        # while adding it to the table to properly perform the join.
        return queries_table + index.query_as_of_now(
            queries_table.query,
            number_of_matches=k,
            metadata_filter=queries_table.metadata_filter
        ).select(
            retrieved_chunks=pw.right.text
        )

if __name__ == "__main__":
    print("NarrativeRetriever module initialized.")
