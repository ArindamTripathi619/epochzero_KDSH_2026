try:
    import sys
    from unittest.mock import MagicMock
    
    # 1. Prepare dummy exception classes that inherit from Exception
    class DummyBeartypeException(Exception): pass
    
    # 2. Mock beartype.roar
    mock_roar = MagicMock()
    mock_roar.BeartypeDecorHintNonpepException = DummyBeartypeException
    mock_roar.BeartypeCallHintParamViolation = DummyBeartypeException
    mock_roar.BeartypeCallHintViolation = DummyBeartypeException
    sys.modules['beartype.roar'] = mock_roar
    
    # 3. Mock beartype
    mock_beartype = MagicMock()
    mock_beartype.beartype = lambda x: x  # Identity decorator
    sys.modules['beartype'] = mock_beartype
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

def extract_true_identity(backstory: str, original_label: str) -> str:
    import requests, os, json, re
    from dotenv import load_dotenv
    load_dotenv()
    API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")
    DUMMY_KEY = os.environ.get("OPENAI_API_KEY", "sk-dummy")
    
    prompt = f"""Identify the central character described in this backstory. 
Return ONLY their primary name (e.g., 'Phileas Fogg'). 
If no clear name is mentioned, return the original label provided.
Original Label: {original_label}
Backstory: {backstory}"""
    
    import random, time
    time.sleep(random.uniform(0.1, 5.0)) # Jitter to prevent burst
    
    try:
        res = requests.post(
            f"{API_BASE}/chat/completions",
             json={"model": "groq-llama-small", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
             headers={"Authorization": f"Bearer {DUMMY_KEY}"},
             timeout=60
        )
        if res.status_code == 200:
            content = res.json()["choices"][0]["message"]["content"].strip().strip('"').strip("'")
            # If the LLM returned too much text, just keep the first few words or fallback
            if len(content.split()) > 4: 
                 return original_label
            return content
    except Exception as e:
        print(f"DEBUG: Identity extraction failed: {e}")
    return original_label

@pw.udf
def run_nli_evaluation(backstory: str, book_character: str, chunks: list, metadata: list, programmatic_results: str, plot_map: str = "") -> tuple[str, str, str]:
    import json, re
    # 1. Programmatic Veto
    try:
         prog = json.loads(programmatic_results)
         if prog.get("verdict") == "Contradictory":
             if "ZERO ENTITY" not in prog.get("reason", ""):
                return "Contradictory", "High", f"PROG-VETO: {prog.get('reason')}"
    except: pass

    # 1.1 Strategy 6: Identity Auto-Correction
    true_identity = extract_true_identity(backstory, book_character)
    if true_identity.lower() != book_character.lower():
        print(f"[STRATEGY 6] Identity Mismatch: CSV says '{book_character}', Backstory describes '{true_identity}'")

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

        # 3. NLI Evaluation (Atomic Claims)
        nli_status, nli_rationale, reranked_chunks = evaluate_backstory_nli(backstory, formatted)
        
        # 3b. Hierarchical Plot Map context (V5.0)
        final_plot_context = plot_map if len(plot_map) > 50 else ""
        
        # 4. LLM Verification — First Pass
        from src.models.llm_judge import ConsistencyJudge, build_consistency_prompt
        judge = ConsistencyJudge()
        evidence_text = "\n".join([f"- [{c['chapter']}] {c['text'][:450]}" for c in reranked_chunks[:20]])
        prompt = build_consistency_prompt(backstory, true_identity, evidence_text, "", final_plot_context)
        
        print(f"DEBUG: Story Verification with Plot Map context... calling LLM Jury.", flush=True)
        res = judge.judge_single(prompt, plot_map=plot_map)
        llm_label = res.get("label", 1)
        llm_rationale = res.get("rationale", "")
        da_score = res.get("da_score", 5)

        # ============================================================
        # 5. DA-Guided Targeted Re-Retrieval (V5.0 — Issue #2 Strategy 3)
        # If DA score is in the ambiguous zone (5-7), find targeted
        # evidence for the specific claim DA is uncertain about,
        # then re-judge with augmented evidence.
        # ============================================================
        if 5 <= da_score <= 7:
            print(f"[DA-RERETRIEVAL] Ambiguous DA score ({da_score}). Searching for targeted evidence...", flush=True)
            try:
                # Extract the claim DA is uncertain about from its rationale
                da_claim = ""
                # Look for DA's direct quote or key claim
                quote_match = re.search(r'DIRECT_QUOTE:\s*(.+?)(?:\||$)', llm_rationale)
                if quote_match:
                    da_claim = quote_match.group(1).strip()
                if not da_claim or len(da_claim) < 10:
                    # Fallback: use the first sentence of the backstory that seems most contentious
                    da_claim = backstory[:300]

                # Use bi-encoder to find the best matching chunks across ALL available evidence
                from sentence_transformers import SentenceTransformer, util
                bi_enc = SentenceTransformer('all-MiniLM-L6-v2')
                all_chunk_texts = [c.decode('utf-8') if isinstance(c, bytes) else str(c) for c in chunks]
                
                if all_chunk_texts:
                    claim_emb = bi_enc.encode(da_claim, convert_to_tensor=True)
                    chunk_embs = bi_enc.encode(all_chunk_texts, convert_to_tensor=True)
                    hits = util.semantic_search(claim_emb, chunk_embs, top_k=5)[0]
                    
                    # Get targeted evidence (top-5 most relevant to the ambiguous claim)
                    targeted_chunks = [all_chunk_texts[hit['corpus_id']] for hit in hits if hit['score'] > 0.20]
                    
                    if targeted_chunks:
                        targeted_evidence = "\n".join([f"- [TARGETED] {tc[:500]}" for tc in targeted_chunks])
                        augmented_evidence = f"{evidence_text}\n\n### ADDITIONAL TARGETED EVIDENCE (for ambiguous claim) ###\n{targeted_evidence}"
                        
                        prompt2 = build_consistency_prompt(backstory, true_identity, augmented_evidence, "", final_plot_context)
                        print(f"[DA-RERETRIEVAL] Re-judging with {len(targeted_chunks)} additional targeted chunks...", flush=True)
                        res2 = judge.judge_single(prompt2, plot_map=plot_map)
                        
                        # Use the re-retrieval result as final
                        llm_label = res2.get("label", llm_label)
                        llm_rationale = f"[RE-RETRIEVAL] {res2.get('rationale', llm_rationale)}"
                        print(f"[DA-RERETRIEVAL] Final verdict after re-retrieval: {'Contradictory' if llm_label == 0 else 'Consistent'}", flush=True)
            except Exception as e:
                print(f"[DA-RERETRIEVAL] Re-retrieval failed: {e}. Keeping original verdict.")

        # Final Verdict
        if llm_label == 0:
            return "Contradictory", "High", f"LLM-JURY ({true_identity}): {llm_rationale}"
        else:
            confidence = "Medium" if nli_status == 1 else "High"
            return "Consistent", confidence, f"LLM-JURY ({true_identity}): {llm_rationale}"

    except Exception as e:
        return "Consistent", "Low", f"Pipeline error: {str(e)}"

@pw.udf
def parse_label(judgment: str) -> int:
    return 0 if (judgment and judgment.lower() == "contradictory") else 1

def run_pipeline():
    # 1. Lifecycle Check: Resumption / Token Protection
    if os.path.exists(OUTPUT_FILE):
        try:
             # Check if output is already complete
             test_df = pd.read_csv(OUTPUT_FILE)
             train_df = pd.read_csv(INPUT_TRAIN_FILE)
             if len(test_df) >= len(train_df):
                  print(f"[LIFECYCLE] {OUTPUT_FILE} already complete ({len(test_df)} stories). Skipping inference phase.")
                  from scripts.calculate_full_accuracy import calculate_full_accuracy
                  calculate_full_accuracy(OUTPUT_FILE, INPUT_TRAIN_FILE)
                  return
             else:
                  print(f"[LIFECYCLE] {OUTPUT_FILE} incomplete ({len(test_df)}/{len(train_df)}). Cleaning up to restart.")
                  os.remove(OUTPUT_FILE)
        except: 
             if os.path.isfile(OUTPUT_FILE): os.remove(OUTPUT_FILE)
             else: import shutil; shutil.rmtree(OUTPUT_FILE)

    # 2. Load Data (STATIC MODE)
    books_table = pw.io.fs.read(INPUT_BOOKS_DIR, format="binary", with_metadata=True, mode="static")
    
    # 3. Extract Chapters (Simplified for speed)
    @pw.udf
    def extract_chapters_list(content: str) -> list[str]:
        import re
        try:
            if isinstance(content, bytes):
                text = content.decode('utf-8', errors='ignore')
            else:
                text = str(content)
            
            # More robust split
            chapters = re.split(r'(?i)^\s*(CHAPTER|PART|BOOK)\s+', text, flags=re.MULTILINE)
            # Filter and clean
            return [c.strip()[:6000] for c in chapters if c and len(c.strip()) > 100]
        except: return []

    flattened_books = books_table.select(
        path=pw.this._metadata["path"],
        chunks=extract_chapters_list(pw.this.data)
    ).flatten(pw.this.chunks)
    
    @pw.udf
    def normalize_book_name(name: str) -> str:
        if not name: return ""
        base = str(name).split("/")[-1]
        return base.lower().replace(".txt", "").strip().strip('"').strip("'").strip()

    books_with_names = flattened_books.select(
        text=pw.this.chunks,
        book_norm=normalize_book_name(pw.this.path)
    )
    
    # 4. Load Train Data (STATIC MODE)
    train_schema = pw.schema_from_csv(INPUT_TRAIN_FILE)
    # Use static mode to ensure auto-termination
    train_table = pw.io.csv.read(INPUT_TRAIN_FILE, schema=train_schema, mode="static").rename(csv_id=pw.this.id)
    
    train_with_names = train_table.select(
        story_id=pw.this.csv_id,
        backstory=pw.this.content,
        character=pw.this.char,
        book_name=pw.this.book_name,
        book_norm=normalize_book_name(pw.this.book_name)
    )
    
    # 5. Retrieval (Vector Search)
    from src.pathway_pipeline.retrieval import NarrativeRetriever
    retriever = NarrativeRetriever(books_dir=INPUT_BOOKS_DIR)

    @pw.udf
    def decompose_claims(backstory: str) -> list[str]:
        import requests, os, json, re
        from dotenv import load_dotenv
        load_dotenv()
        API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")
        DUMMY_KEY = os.environ.get("OPENAI_API_KEY", "sk-dummy")
        
        prompt = f"""Decompose this backstory into 6-8 independent, atomic, and testable claims. 
        Each claim should be a single, standalone sentence.
        Format your response as a simple JSON list of strings.
        
        Backstory: {backstory}"""
        
        import random, time
        time.sleep(random.uniform(0.1, 5.0)) # Jitter to prevent burst

        try:
            res = requests.post(
                f"{API_BASE}/chat/completions",
                json={"model": "groq-llama-small", "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
                headers={"Authorization": f"Bearer {DUMMY_KEY}"},
                timeout=60
            )
            if res.status_code == 200:
                content = res.json()["choices"][0]["message"]["content"]
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    claims = json.loads(match.group(0))
                    # Quality filter: remove very short or trivial claims
                    return [str(c) for c in claims if len(str(c)) > 15]
        except Exception as e:
            print(f"DEBUG: Claim decomposition failed: {e}")
        
        # Fallback: simple split if LLM fails
        return [s.strip() for s in backstory.split('.') if len(s.strip()) > 15]
        return [backstory]

    query_table_lists = train_with_names.select(
        *pw.this,
        claims=decompose_claims(pw.this.backstory)
    )

    flat_queries = query_table_lists.flatten(pw.this.claims).select(
        *pw.this,
        single_claim=pw.this.claims
    )

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
    
    # 6. Load Hierarchical Plot Maps (V5.0 — generated once, cached on disk)
    plot_maps = {}
    plot_maps_dir = "Dataset/PlotMaps/"
    if os.path.exists(plot_maps_dir):
        for pm_file in os.listdir(plot_maps_dir):
            if pm_file.endswith("_plot_map.txt"):
                book_key = pm_file.replace("_plot_map.txt", "").lower().strip()
                with open(os.path.join(plot_maps_dir, pm_file), 'r', encoding='utf-8') as f:
                    plot_maps[book_key] = f.read()
        print(f"[V5.0] Loaded {len(plot_maps)} Plot Maps: {list(plot_maps.keys())}")
    else:
        print(f"[V5.0] WARNING: No Plot Maps directory found at {plot_maps_dir}")

    @pw.udf
    def get_plot_map(book_name: str) -> str:
        """Look up the pre-generated plot map for a book."""
        if not book_name:
            return ""
        # Normalize: "The Count of Monte Cristo.txt" → "the count of monte cristo"
        norm = book_name.lower().replace(".txt", "").strip().strip('"').strip("'")
        # Try direct match first, then substring match
        if norm in plot_maps:
            return plot_maps[norm]
        for key, val in plot_maps.items():
            if norm in key or key in norm:
                return val
        return ""

    # 7. Reasoning
    reasoning_table = joined_table.select(
        *pw.this,
        plot_map=get_plot_map(pw.this.book_name),
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
            pw.this.character,
            pw.this.chunks,
            pw.this.metadata,
            pw.this.programmatic_results,
            pw.this.plot_map  # V5.0: Pass the Hierarchical Plot Map!
        )
    ).select(
        *pw.this,
        judgment=pw.this.judgment_data[0],
        confidence=pw.this.judgment_data[1],
        rationale=pw.this.judgment_data[2]
    )

    # 7. Final Output
    output_table = judged_table.select(
        **{"Story ID": pw.this.story_id},
        Prediction=parse_label(pw.this.judgment),
        Rationale=pw.this.rationale,
        Confidence=pw.this.confidence
    )
    
    pw.io.csv.write(output_table, OUTPUT_FILE)
    print(f"[LIFECYCLE] Executing Ensemble Inference (Static Pass)...")
    
    # In static mode, pw.run() terminates when data flows through
    pw.run()
    
    # 8. Post-Run AUTOMATED EVALUATION
    try:
        if os.path.exists(OUTPUT_FILE):
             print(f"\n[LIFECYCLE] Inference Complete. Formatting {OUTPUT_FILE}...")
             # Filter Pathway internal cols
             df = pd.read_csv(OUTPUT_FILE)
             cols = ["Story ID", "Prediction", "Rationale", "Confidence"]
             final_df = df[[c for c in cols if c in df.columns]]
             final_df.to_csv(OUTPUT_FILE, index=False)
             
             # TRIGGER ACCURACY
             from scripts.calculate_full_accuracy import calculate_full_accuracy
             calculate_full_accuracy(OUTPUT_FILE, INPUT_TRAIN_FILE)
             print(f"[LIFECYCLE] Pipeline session closed successfully.")
    except Exception as e:
        print(f"[ERROR] Post-processing/Evaluation failed: {e}")

if __name__ == "__main__":
    run_pipeline()
