import pathway as pw
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.stdlib.indexing.nearest_neighbors import BruteForceKnnFactory
from pathway.xpacks.llm.embedders import SentenceTransformerEmbedder
import inspect

def final_inspect():
    # Setup minimal store
    docs = pw.io.fs.read(".", format="binary", mode="static")
    embedder = SentenceTransformerEmbedder(model="all-MiniLM-L6-v2")
    rf = BruteForceKnnFactory(embedder=embedder)
    ds = DocumentStore(docs=docs, retriever_factory=rf)
    
    print("Full signature of retrieve_query:", inspect.signature(ds.retrieve_query))
    
    # Also check the code if possible
    try:
        print("Source of retrieve_query:")
        print(inspect.getsource(ds.retrieve_query))
    except:
        print("Could not get source")

if __name__ == "__main__":
    final_inspect()
