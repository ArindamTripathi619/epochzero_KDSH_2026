try:
    import beartype
    from unittest.mock import MagicMock
    import sys
    # Bypass beartype decorators and roar exceptions for Python 3.14 compatibility
    mock_beartype = MagicMock()
    mock_beartype.beartype = lambda x: x  # Identity decorator
    sys.modules['beartype'] = mock_beartype
    
    mock_roar = MagicMock()
    # Define the specific exception Pathway expects
    class BeartypeDecorHintNonpepException(Exception): pass
    mock_roar.BeartypeDecorHintNonpepException = BeartypeDecorHintNonpepException
    sys.modules['beartype.roar'] = mock_roar
except ImportError:
    pass

import pathway as pw
import pandas as pd
import os
import json
import spacy
from typing import List, Dict, Tuple

# Configuration
INPUT_BOOKS_DIR = "Dataset/Books/"
INPUT_TRAIN_FILE = "Dataset/train_fixed.csv"
OUTPUT_FILE = "results.csv"

# Global entities/tracker imports for top-level if needed (though we rely on UDF internal imports)
try:
    from src.reasoning.entity_tracker import EntityStateTracker
    from src.reasoning.timeline_validator import TimelineValidator
    from src.reasoning.constraint_rules import ConstraintRules
except ImportError:
    pass

@pw.udf
def perform_programmatic_reasoning(backstory: str, chunks: list, metadata: list, book_name: str) -> str:
    import json
    import spacy
    print(f"[DEBUG] Programmatic reasoning for a backstory (book: {book_name})")
    try:
        from src.reasoning.entity_tracker import EntityStateTracker
        from src.reasoning.timeline_validator import TimelineValidator
        from src.reasoning.constraint_rules import ConstraintRules
        
        tracker = EntityStateTracker()
        validator = TimelineValidator()
        rules = ConstraintRules()
        
        # 1. Claims
        from src.models.nli_judge import get_nlp
        nlp = get_nlp()
        doc = nlp(backstory)
        backstory_claims = [sent.text for sent in doc.sents]
        
        # 2. Evidence
        valid_chunks = [c.decode('utf-8') if isinstance(c, bytes) else str(c) for c in chunks]
        narrative_states = []
        for i, text in enumerate(valid_chunks):
             meta = metadata[i] if metadata and i < len(metadata) else {}
             try:
                  chapter = dict(meta).get("chapter", "Unknown") if meta else "Unknown"
             except: chapter = "Unknown"
             narrative_states.append({"text": text, "chapter": chapter})
             
        # 3. Overlap
        backstory_ents = tracker.extract_basic_entities(backstory)
        bs_ents_list = backstory_ents.get("PERSON", []) + backstory_ents.get("GPE", []) + backstory_ents.get("LOC", [])
        bs_proper_nouns = {w.lower() for w in bs_ents_list if len(w) > 3}
        
        evidence_text = " ".join(valid_chunks).lower()
        overlap = any(noun in evidence_text for noun in bs_proper_nouns)
        
        all_conflicts = []
        # Refined Overlap Check: Only flag if many entities and ZERO overlap
        if len(bs_proper_nouns) >= 3 and not overlap and book_name:
             all_conflicts.append(f"ZERO ENTITY OVERLAP: {list(bs_proper_nouns)[:3]}")
        
        all_conflicts.extend(validator.validate_location_consistency(backstory_claims, narrative_states))
        all_conflicts.extend(rules.check_imprisonment_constraint(backstory_claims, narrative_states))
        all_conflicts.extend(rules.check_death_constraint(backstory_claims, narrative_states))

        verdict = "Contradictory" if all_conflicts else "Consistent"
        return json.dumps({"verdict": verdict, "reason": " | ".join(all_conflicts[:2])})
    except Exception as e:
        return json.dumps({"verdict": "Consistent", "reason": f"Programmatic Error: {str(e)}"})

@pw.udf
def run_nli_evaluation(backstory: str, chunks: list, metadata: list, programmatic_results: str) -> tuple[str, str, str]:
    import json
    # 1. Programmatic Veto
    try:
         prog = json.loads(programmatic_results)
         if prog.get("verdict") == "Contradictory":
             if "ZERO ENTITY" not in prog.get("reason", ""):
                return "Contradictory", "High", f"PROG-VETO: {prog.get('reason')}"
    except: pass

    # 2. Format chunks for evaluation
    try:
        from src.models.nli_judge import evaluate_backstory_nli
        formatted = []
        for i, c in enumerate(chunks):
             text = c.decode('utf-8') if isinstance(c, bytes) else str(c)
             meta = metadata[i] if metadata and i < len(metadata) else {}
             try: chapter = dict(meta).get("chapter", "Unknown") if meta else "Unknown"
             except: chapter = "Unknown"
             formatted.append({"text": text, "chapter": chapter})

        # 3. NLI Evaluation (Atomic Claims) - Now returns reranked_chunks
        nli_status, nli_rationale, reranked_chunks = evaluate_backstory_nli(backstory, formatted)
        
        # Strategy 3: Mini Plot-Map Summarization
        plot_summary = ""
        try:
             plot_summary_prompt = "Write a 500-word plot summary of the events described in these chunks. Include Key character arcs, Major timeline anchors, and Central causal events:\n\n"
             for c in formatted[:30]:
                  plot_summary_prompt += f"[{c['chapter']}] {c['text'][:300]}\n"

             import requests, os
             from dotenv import load_dotenv
             load_dotenv()
             apiKey = os.environ.get("OPENAI_API_KEY", "sk-dummy")
             res = requests.post(
                 "http://localhost:8000/v1/chat/completions",
                 json={"model": "groq-scout", "messages": [{"role": "user", "content": plot_summary_prompt}]},
                 headers={"Authorization": f"Bearer {apiKey}"},
                 timeout=20
             )
             if res.status_code == 200:
                  plot_summary = res.json()["choices"][0]["message"]["content"]
        except Exception as e:
             print(f"DEBUG: Plot summary failed: {e}")

        # 4. LLM Verification (Mandatory for ALL stories in Strategy 3)
        from src.models.llm_judge import ConsistencyJudge, build_consistency_prompt
        judge = ConsistencyJudge()
        # FIX: Use reranked_chunks and increase window to 20
        evidence_text = "\n".join([f"- [{c['chapter']}] {c['text'][:400]}" for c in reranked_chunks[:20]])
        prompt = build_consistency_prompt(backstory, "Character", evidence_text, "", plot_summary)
        
        print(f"DEBUG: Processing Story ID {backstory[:20]}... calling LLM judge.", flush=True)
        res = judge.judge_single(prompt)
        llm_label = res.get("label", 1)
        llm_rationale = res.get("rationale", "")
        
        # Final Verdict based primarily on LLM
        if llm_label == 0:
            return "Contradictory", "High", f"LLM-FIRST VERIFIED: {llm_rationale} | NLI_REF: {nli_rationale}"
        else:
            confidence = "Medium" if nli_status == 1 else "High"
            return "Consistent", confidence, f"LLM-FIRST CONSISTENT: {llm_rationale} | NLI_REF: {nli_rationale}"

    except Exception as e:
        return "Consistent", "Low", f"Pipeline error: {str(e)}"

@pw.udf
def parse_label(judgment: str) -> int:
    return 0 if (judgment and judgment.lower() == "contradictory") else 1

def run_pipeline():
    # 1. Load Data
    books_table = pw.io.fs.read(INPUT_BOOKS_DIR, format="binary", with_metadata=True)
    
    # 2. Extract Chapters (Simplified for speed)
    @pw.udf
    def extract_chapters_list(content: str) -> list[str]:
        import re
        try:
            if isinstance(content, bytes):
                text = content.decode('utf-8', errors='ignore')
            else:
                text = str(content)
            
            chapters = re.split(r'(?i)CHAPTER', text)
            return [c.strip()[:5000] for c in chapters if c and len(c.strip()) > 50]
        except Exception as e:
            return []

    # 2. Process books
    flattened_books = books_table.select(
        path=pw.this._metadata["path"],
        chunks=extract_chapters_list(pw.this.data)
    ).flatten(pw.this.chunks)
    
    # DEBUG: Write flattened
    pw.io.csv.write(flattened_books, "debug_flattened.csv")
    
    @pw.udf
    def normalize_book_name(name: str) -> str:
        if not name: return ""
        # Handle both full paths and raw names
        base = str(name).split("/")[-1]
        return base.lower().replace(".txt", "").strip().strip('"').strip("'").strip()

    books_with_names = flattened_books.select(
        text=pw.this.chunks,
        book_norm=normalize_book_name(pw.this.path)
    )
    
    # DEBUG: Write normalized books
    pw.io.csv.write(books_with_names, "debug_books.csv")
    
    # 3. Load Train Data
    train_schema = pw.schema_from_csv(INPUT_TRAIN_FILE)
    # Force partitioned directory if present for better flushing
    INCR_DATA = "Dataset/train_parts/"
    actual_input = INCR_DATA if os.path.exists(INCR_DATA) else INPUT_TRAIN_FILE
    
    print(f"[DEBUG] Reading from: {actual_input}")
    train_table = pw.io.csv.read(actual_input, schema=train_schema).rename(csv_id=pw.this.id)
    
    train_with_names = train_table.select(
        story_id=pw.this.csv_id,
        backstory=pw.this.content,
        character=pw.this.char,
        book_name=pw.this.book_name,
        book_norm=normalize_book_name(pw.this.book_name)
    )
    
    # DEBUG: Write normalized train data
    pw.io.csv.write(train_with_names, "debug_train.csv")

    # 4. Retrieval (Vector Search)
    from src.pathway_pipeline.retrieval import NarrativeRetriever
    retriever = NarrativeRetriever(books_dir=INPUT_BOOKS_DIR)

    @pw.udf
    def decompose_claims(backstory: str) -> list[str]:
        import requests, os, json, re
        from dotenv import load_dotenv
        load_dotenv()
        API_BASE = "http://localhost:8000/v1"
        DUMMY_KEY = os.environ.get("OPENAI_API_KEY", "sk-dummy")
        prompt = f"Decompose this backstory into 5 to 8 atomic, standalone claims. Return ONLY a JSON list of strings.\nBackstory: {backstory}"
        try:
            res = requests.post(
                f"{API_BASE}/chat/completions",
                 json={"model": "groq-llama-small", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
                 headers={"Authorization": f"Bearer {DUMMY_KEY}"},
                 timeout=15
            )
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    claims = json.loads(match.group(0))
                    if isinstance(claims, list) and len(claims) > 0:
                        return [str(c) for c in claims]
        except Exception as e:
            print(f"DEBUG: Claim decomposition failed: {e}")
        return [backstory]

    query_table_lists = train_with_names.select(
        *pw.this,
        claims=decompose_claims(pw.this.backstory)
    )

    flat_queries = query_table_lists.flatten(pw.this.claims).select(
        *pw.this,
        single_claim=pw.this.claims
    )

    @pw.udf
    def calculate_adaptive_k(backstory: str) -> int:
        return 20  # 20 chunks per claim

    # Vector search per claim
    joined_flat = retriever.retrieve(
        flat_queries.select(
            pw.this.story_id, 
            pw.this.backstory, 
            pw.this.character, 
            pw.this.book_name, 
            query=pw.this.single_claim
        ), 
        k=20
    )

    grouped_table = joined_flat.groupby(pw.this.story_id).reduce(
        story_id=pw.this.story_id,
        backstory=pw.reducers.min(pw.this.backstory),
        character=pw.reducers.min(pw.this.character),
        book_name=pw.reducers.min(pw.this.book_name),
        metadata_tup=pw.reducers.tuple(pw.this.retrieved_metadata),
        chunks_tup=pw.reducers.tuple(pw.this.retrieved_chunks)
    )

    @pw.udf
    def flatten_retrieved(nested_chunks: tuple, nested_metadata: tuple) -> tuple[list, list]:
         flat_c, flat_m = [], []
         seen = set()
         for t_c, t_m in zip(nested_chunks, nested_metadata):
              if t_c and t_m:
                  for c, m in zip(t_c, t_m):
                       c_str = c.decode('utf-8') if isinstance(c, bytes) else str(c)
                       if c_str not in seen:
                            seen.add(c_str)
                            flat_c.append(c)
                            flat_m.append(m)
         return flat_c, flat_m

    joined_table = grouped_table.select(
        *pw.this,
        flat_results=flatten_retrieved(pw.this.chunks_tup, pw.this.metadata_tup)
    ).select(
        story_id=pw.this.story_id,
        backstory=pw.this.backstory,
        character=pw.this.character,
        book_name=pw.this.book_name,
        metadata=pw.this.flat_results[1],
        chunks=pw.this.flat_results[0]
    )
    
    # DEBUG: Write joined rows
    pw.io.csv.write(joined_table, "debug_joined.csv")

    # 5. Reasoning
    reasoning_table = joined_table.select(
        *pw.this,
        programmatic_results=perform_programmatic_reasoning(
            pw.this.backstory,
            pw.this.chunks,
            pw.this.metadata,
            pw.this.book_name
        )
    )

    judged_table = reasoning_table.select(
        *pw.this,
        judgment_data=run_nli_evaluation(
            pw.this.backstory,
            pw.this.chunks,
            pw.this.metadata,
            pw.this.programmatic_results
        )
    ).select(
        *pw.this,
        judgment=pw.this.judgment_data[0],
        confidence=pw.this.judgment_data[1],
        rationale=pw.this.judgment_data[2]
    )

    # 6. Final Output
    output_table = judged_table.select(
        **{"Story ID": pw.this.story_id},
        Prediction=parse_label(pw.this.judgment),
        Rationale=pw.this.rationale,
        Confidence=pw.this.confidence
    )

    # 7. Write and Run (incremental if INPUT_DATA is directory)
    if os.path.exists(OUTPUT_FILE):
        if os.path.isfile(OUTPUT_FILE): os.remove(OUTPUT_FILE)
        else: import shutil; shutil.rmtree(OUTPUT_FILE)
        
    pw.io.csv.write(output_table, OUTPUT_FILE)
    print(f"[DEBUG] Starting Pipeline execution (incremental mode)...")
    
    pw.run()
    
    # post-process for clean CSV
    try:
        if os.path.exists(OUTPUT_FILE):
             # Filter Pathway internal cols
             df = pd.read_csv(OUTPUT_FILE)
             cols = ["Story ID", "Prediction", "Rationale", "Confidence"]
             final_df = df[[c for c in cols if c in df.columns]]
             final_df.to_csv(OUTPUT_FILE, index=False)
             print(f"[SUCCESS] Results written to {OUTPUT_FILE}")
    except Exception as e:
        print(f"[ERROR] Post-processing failed: {e}")

if __name__ == "__main__":
    run_pipeline()
