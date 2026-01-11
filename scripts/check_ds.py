import pathway as pw
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.embedders import SentenceTransformerEmbedder

def check_methods():
    # Setup minimal store
    docs = pw.io.fs.read(".", format="binary", mode="static")
    embedder = SentenceTransformerEmbedder(model="all-MiniLM-L6-v2")
    rf = BruteForceKnnFactory(embedder=embedder)
    store = DocumentStore(docs=docs, retriever_factory=rf)
    
    print("DocumentStore methods:", [m for m in dir(store) if not m.startswith("_")])
    if hasattr(store, "as_retriever"):
        print("as_retriever exists")
    
    # Check what store._retriever has
    print("Retriever methods:", [m for m in dir(store._retriever) if not m.startswith("_")])

if __name__ == "__main__":
    check_methods()
