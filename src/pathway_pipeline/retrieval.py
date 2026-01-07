import os
import pathway as pw
import re
from typing import Optional
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.xpacks.llm.embedders import SentenceTransformerEmbedder
from pathway.xpacks.llm.splitters import TokenCountSplitter


class StrParser:
    """Simple parser for data that is already string."""
    def __call__(self, text: str):
        return [(text, {})]


class NarrativeRetriever:
    def __init__(self, books_dir: str, embedder_model: str = "all-MiniLM-L6-v2"):
        self.books_dir = books_dir
        
        # 1. Ingest novels
        # Pathway's fs.read handles local directory ingestion
        raw_files = pw.io.fs.read(
            self.books_dir,
            format="binary",
            with_metadata=True,
            mode="static"
        )
        
        print(f"[DEBUG] Ingested {raw_files.schema} - Raw files loaded")

        # 1.1 Custom UDF to parse Reference Metadata (Chapter, Progress)
        @pw.udf
        def split_by_chapter(data: bytes, metadata: dict) -> list[tuple[str, dict]]:
            try:
                text = data.decode("utf-8")
            except:
                return [("", {})]
            
            # Access path from metadata (handle Pathway Json object)
            try:
                # Convert Json wrapper to string and clean quotes if present
                path_val = metadata["path"]
                path = str(path_val).strip('"')
            except:
                path = "Unknown Source"
            
            # Ensure path is never None
            if path is None:
                path = "Unknown Source"
            
            # Basic Chapter DetectionRegex
            # Matches "CHAPTER I", "Chapter 1", "I.", etc. strictly at start of lines
            # This is heuristic and might need tuning for specific books. Now expanded to include "Part", "Book", etc.
            chapter_pattern = r'(?m)^(?:CHAPTER|Chapter|PART|Part|BOOK|Book)\s+(?:[IVXLCDM\d]+|[A-Z]+).*$'
            
            matches = list(re.finditer(chapter_pattern, text))
            if not matches:
                # Fallback if no chapters found: treat whole book as one "Chapter"
                return [(text, {"chapter": "Full Text", "progress_pct": 0.0, "path": path})]
            
            chunks = []
            total_len = len(text)
            
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i+1].start() if i+1 < len(matches) else len(text)
                
                # Content includes the header
                chapter_content = text[start:end]
                chapter_title = match.group(0).strip()
                
                # Approximate progress
                progress = round((start / total_len) * 100, 1)
                
                chunks.append((
                    chapter_content, 
                    {
                        "chapter": chapter_title,
                        "progress_pct": progress,
                        "source_file": path.split("/")[-1],
                        "path": path  # Keep original path for filter compatibility
                    }
                ))
            
            # Handle prologue/preamble (text before first chapter)
            if matches[0].start() > 0:
                preamble = text[:matches[0].start()]
                if len(preamble.strip()) > 100:
                    chunks.insert(0, (preamble, {"chapter": "Preamble", "progress_pct": 0.0, "source_file": path.split("/")[-1], "path": path}))
                    
            return chunks

        # Apply splitting and flattening
        chapters_table = raw_files.select(
            chunks=split_by_chapter(pw.this.data, pw.this._metadata)
        ).flatten(pw.this.chunks).select(
            data=pw.this.chunks[0],
            metadata=pw.this.chunks[1]
        )
        
        # CRITICAL: Ensure 'path' is always a valid string in metadata
        # DocumentStore will use this metadata column, so we must guarantee non-null values
        @pw.udf
        def ensure_path_in_metadata(meta: dict) -> dict:
            """Ensure metadata has a valid 'path' field for JMESPath filtering."""
            if not isinstance(meta, dict):
                return {"path": "Unknown", "chapter": "Unknown", "progress_pct": 0}
            
            # Ensure path exists and is never None or empty
            if "path" not in meta or meta["path"] is None or meta["path"] == "":
                meta["path"] = "Unknown"
            
            return meta
        
        chapters_table = chapters_table.select(
            data=pw.this.data,
            metadata=ensure_path_in_metadata(pw.this.metadata)
        )
        
        print(f"[DEBUG] Chapters table schema: {chapters_table.schema}")
        print(f"[DEBUG] Metadata sanitization complete - proceeding to DocumentStore")
        
        # 2. Setup Indexing Components
        self.embedder = SentenceTransformerEmbedder(model=embedder_model)
        
        self.retriever_factory = BruteForceKnnFactory(
            embedder=self.embedder,
        )
        
        self.text_splitter = TokenCountSplitter(
            min_tokens=200,
            max_tokens=600,
            encoding_name="cl100k_base"
        )
        
        # Parser is now effectively checking types or doing final cleanup
        self.parser = StrParser()
        
        # 3. Create Document Store
        # Note: DocumentStore will further split these "Chapter chunks" into smaller token chunks
        # Importantly, it SHOULD preserve the 'metadata' column we created above.
        self.store = DocumentStore(
            docs=chapters_table,
            retriever_factory=self.retriever_factory,
            parser=self.parser,
            splitter=self.text_splitter,
        )

    def retrieve(self, queries_table: pw.Table, k: int = 5):
        """
        Retrieves relevant book chunks using lower-level query_as_of_now.
        NOTE: We removed metadata_filter from here due to null path issues.
        Filtering by book will be done post-retrieval in main.py.
        """
        index = self.store._retriever
        
        # We MUST select from the JoinResult returned by query_as_of_now 
        # while adding it to the table to properly perform the join.
        # REMOVED: metadata_filter=queries_table.metadata_filter (causing null path errors)
        return queries_table + index.query_as_of_now(
            queries_table.query,
            number_of_matches=k
        ).select(
            retrieved_chunks=pw.right.text,
            retrieved_metadata=pw.right.metadata  # <--- Capture the metadata for post-filtering
        )

if __name__ == "__main__":
    print("NarrativeRetriever module initialized.")
