
import pathway as pw
import pandas as pd
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.embedders import SentenceTransformerEmbedder

def debug_query_sig():
    # Setup minimal store
    docs = pw.io.fs.read(".", format="binary", mode="static")
    embedder = SentenceTransformerEmbedder(model="all-MiniLM-L6-v2")
    rf = BruteForceKnnFactory(embedder=embedder)
    store = DocumentStore(docs=docs, retriever_factory=rf)
    
    import inspect
    print("DataIndex.query signature:", inspect.signature(store._retriever.query))

if __name__ == "__main__":
    debug_query_sig()
