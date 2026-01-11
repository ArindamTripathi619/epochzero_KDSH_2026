import pathway as pw
import re
import os
import json
from typing import Any, List, Tuple
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.embedders import SentenceTransformerEmbedder
from pathway.xpacks.llm.splitters import TokenCountSplitter
from pathway.xpacks.llm.parsers import ParseUtf8

# Configuration (could be moved to a separate config file)
BOOKS_DIR = "Dataset/Books/"

class NarrativeRetriever:
    """
    Handles book ingestion, splitting, and retrieval.
    """
    def __init__(self, books_dir: str, embedder_model: str = "all-MiniLM-L6-v2"):
        self.books_dir = books_dir

        # 1. Ingest novels
        raw_files = pw.io.fs.read(
            self.books_dir,
            format="binary",
            with_metadata=True,
            mode="static"
        )
        
        print(f"[DEBUG] Ingested {raw_files.schema} - Raw files loaded")

        # 1.1 Custom UDF to parse Reference Metadata (Chapter, Progress)
        @pw.udf
        def split_by_chapter(data: bytes, metadata: dict) -> List[Tuple[Any, dict]]:
            try:
                text = data.decode("utf-8", errors="ignore")
            except:
                return []
            
            # Handle Json metadata object cleanly
            try:
                path = metadata["path"] if "path" in metadata else "Unknown"
            except:
                path = "Unknown"
            
            # Simple heuristic chapter splitting (Standard in Gutenberg/Novel formats)
            # Improved to handle CRLF (\r\n) and optional formatting
            chapter_pattern = r"(?i)^\s*(CHAPTER|PART|BOOK)\s+[IVXLCDM\d]+.*$"
            matches = list(re.finditer(chapter_pattern, text, re.MULTILINE))
            
            if not matches:
                return [(text.encode("utf-8"), {"chapter": "Full Text", "progress_pct": 0.0, "path": path})]
            
            chunks = []
            total_len = len(text)
            
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i+1].start() if i+1 < len(matches) else len(text)
                chapter_content = text[start:end].strip()
                chapter_title = match.group(0).strip()
                progress = round((start / total_len) * 100, 1)
                
                chunks.append((
                    chapter_content.encode("utf-8"), 
                    {
                        "chapter": chapter_title,
                        "progress_pct": progress,
                        "source_file": path.split("/")[-1],
                        "path": path
                    }
                ))
            
            if matches[0].start() > 0:
                preamble = text[:matches[0].start()]
                if len(preamble.strip()) > 100:
                    chunks.insert(0, (preamble.encode("utf-8"), {"chapter": "Preamble", "progress_pct": 0.0, "source_file": path.split("/")[-1], "path": path}))
                    
            return chunks

        # Apply splitting and flattening
        chapters_table = raw_files.select(
            chunks=split_by_chapter(pw.this.data, pw.this._metadata)
        ).flatten(pw.this.chunks).select(
            data=pw.this.chunks[0],
            _metadata=pw.this.chunks[1]
        )

        @pw.udf
        def ensure_path_in_metadata(meta: any) -> dict:
            if meta is None:
                return {"path": "unknown_path"}
            try:
                if hasattr(meta, "as_dict"):
                    new_meta = meta.as_dict()
                elif hasattr(meta, "to_dict"):
                    new_meta = meta.to_dict()
                else:
                    new_meta = {}
                    for k in meta:
                        new_meta[str(k)] = meta[k]
            except:
                new_meta = {}
            if "path" not in new_meta or new_meta["path"] is None:
                new_meta["path"] = "unknown_path"
            return new_meta

        chapters_table = chapters_table.select(
            data=pw.this.data,
            _metadata=ensure_path_in_metadata(pw.this._metadata)
        )

        print(f"[DEBUG] Chapters table schema: {chapters_table.schema}")
        print("[DEBUG] Metadata sanitization complete - proceeding to DocumentStore")

        # 2. Setup Indexing Components
        self.embedder = SentenceTransformerEmbedder(model=embedder_model)
        self.retriever_factory = BruteForceKnnFactory(embedder=self.embedder)
        self.text_splitter = TokenCountSplitter(min_tokens=200, max_tokens=600, encoding_name="cl100k_base")
        self.parser = ParseUtf8()

        # 3. Create Document Store
        self.store = DocumentStore(
            docs=chapters_table,
            retriever_factory=self.retriever_factory,
            parser=self.parser,
            splitter=self.text_splitter,
        )
        print(f"[DEBUG] DocumentStore created.")

    def retrieve(self, queries_table: pw.Table, k: int = 20):
        """
        Retrieves relevant book chunks using lower-level query_as_of_now.
        """
        # index = self.store._retriever
        # Direct access to the internal retriever to use query_as_of_now
        results = self.store._retriever.query_as_of_now(queries_table.query, k)

        return queries_table + results.select(
            retrieved_chunks=pw.this.text,
            retrieved_metadata=pw.this.metadata
        )

if __name__ == "__main__":
    print("NarrativeRetriever module initialized.")
