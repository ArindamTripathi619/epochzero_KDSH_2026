import pathway as pw
import pandas as pd
import os
import json
import spacy
from typing import List, Dict, Tuple

# Configuration
INPUT_BOOKS_DIR = "Dataset/Books/"
INPUT_TRAIN_FILE = "Dataset/train.csv"
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

        # 3. NLI Evaluation (Atomic Claims)
        status, rationale = evaluate_backstory_nli(backstory, formatted)
        
        # If NLI says consistent → trust it
        if status == 1:
            return "Consistent", "Medium", rationale
            
        # NLI flagged contradiction → verify with CoT LLM
        from src.models.llm_judge import ConsistencyJudge, build_consistency_prompt
        judge = ConsistencyJudge()
        evidence_text = "\n".join([f"- [{f['chapter']}] {f['text'][:400]}" for f in formatted[:12]])
        prompt = build_consistency_prompt(backstory, "Character", evidence_text, "")
        res = judge.judge_single(prompt)
        llm_label = res.get("label", 1)
        llm_rationale = res.get("rationale", "")
        
        if llm_label == 0:
            return "Contradictory", "Very High", f"NLI+LLM VERIFIED: {llm_rationale}"
        else:
            return "Consistent", "High", f"LLM OVERTURNED: {llm_rationale}"

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
    def expand_query(character: str, backstory: str) -> str:
        base = f"{character} {backstory}"
        import re
        words = re.findall(r'\b[A-Za-z]{5,}\b', backstory)
        keywords = " ".join(words[:15]) if words else backstory
        
        # Conflict triggers
        conflict_seeds = ""
        back_lower = backstory.lower()
        if any(w in back_lower for w in ["imprison", "jail", "cell", "prison", "arrest"]):
            conflict_seeds = "confinement dungeon captive prisoner arrest"
        elif any(w in back_lower for w in ["died", "death", "killed", "passed", "murder"]):
            conflict_seeds = "deceased burial tomb funeral corpse"
        elif "born" in back_lower or "birth" in back_lower:
            conflict_seeds = "parents childhood origin ancestry"

        return f"{base} {keywords} {conflict_seeds}"

    query_table = train_with_names.select(
        *pw.this,
        query=expand_query(pw.this.character, pw.this.backstory)
    )

    @pw.udf
    def calculate_adaptive_k(backstory: str) -> int:
        # Increase k to 50 to give the NLI Reranker more material to work with
        return 50

    # Vector search instead of simple join
    joined_table = retriever.retrieve(
        query_table, 
        k=calculate_adaptive_k(query_table.backstory)
    ).select(
        story_id=pw.this.story_id,
        backstory=pw.this.backstory,
        character=pw.this.character,
        book_name=pw.this.book_name,
        chunks=pw.this.retrieved_chunks,
        metadata=pw.this.retrieved_metadata
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
