# Pathway v23 Migration Guide: Narrative Consistency Refactor

This document details the technical changes required to support Pathway v23.0.x (released late 2024/early 2025) for the Narrative Consistency project.

## 1. Deprecation of DocumentStore (XPack)
The `pathway.xpacks.llm.document_store` module, which was standard in v20-v22, has been deprecated and largely removed in v23 in favor of a more flexible `VectorStoreServer` architecture.

### Old Logic (v22 and below):
```python
from pathway.xpacks.llm.document_store import DocumentStore
store = DocumentStore(
    data,
    embedding_model=model,
    # ...
)
results = store.query_as_of_now(query_text, k=3)
```

### New Logic (v23+):
```python
from pathway.xpacks.llm.vector_store import VectorStoreServer
vector_store = VectorStoreServer(
    data,
    embedder=embedder,
    # ...
)
# Note: query_as_of_now is replaced by .query()
results = vector_store.query(query_text, k=3)
```

## 2. API Shifts
| Feature | v22 Method | v23 Method |
|---------|------------|------------|
| Querying | `query_as_of_now()` | `.query()` |
| Initialization | `DocumentStore()` | `VectorStoreServer()` |
| Result Retrieval | `pw.right.data` | `pw.this.data` (Internal Join mapping) |

## 3. The `pw.this.data` Join Challenge
In v23, the internal schema mapping for `VectorStoreServer` results changed how columns are joined back to the query table.

In `src/pathway_pipeline/retrieval.py`, we had to refactor the join logic:
- **Old**: Relied on `pw.right.text` or similar implicit pointers.
- **New**: Explicitly map to `pw.this.data` when processing search results within the Pathway stream.

## 4. Cross-Encoder Integration
v23 provides better support for re-rankers. We maintained the cross-encoder integration within the `NarrativeRetriever` wrapper class to ensure high-precision context retrieval before passing evidence to the LLM judges.
