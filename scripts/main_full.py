import os
import json
import pathway as pw
import pandas as pd
from src.pathway_pipeline.retrieval import NarrativeRetriever
from src.models.llm_judge import ConsistencyJudge, build_consistency_prompt
from src.reasoning.entity_tracker import EntityStateTracker
from src.reasoning.timeline_validator import TimelineValidator
from src.reasoning.constraint_rules import ConstraintRules

# Constants
BOOKS_DIR = "Dataset/Books/"
TRAIN_DATA = os.getenv("INPUT_DATA", "Dataset/test.csv")
OUTPUT_FILE = "results.csv"

def main():
    # 1. Initialize Components
    retriever = NarrativeRetriever(books_dir=BOOKS_DIR)
    # LLM selection is now driven by env vars (USE_CLOUD, LLM_MODEL)
    judge = ConsistencyJudge()

    # 2. Load Queries
    # PRE-PROCESSING HACK: Pathway hijacks any column named 'id' as a pointer.
    # We rename it to 'story_id_numeric' in a temporary file to preserve the values.
    temp_data_path = TRAIN_DATA + ".tmp"
    try:
        df_input = pd.read_csv(TRAIN_DATA)
        if 'id' in df_input.columns:
            df_input.rename(columns={'id': 'story_id_numeric'}, inplace=True)
        df_input.to_csv(temp_data_path, index=False)
    except Exception as e:
        print(f"[ERROR] Pre-processing failed: {e}")
        temp_data_path = TRAIN_DATA

    query_schema = pw.schema_from_csv(temp_data_path)
    
    queries = pw.io.csv.read(
        temp_data_path,
        schema=query_schema,
        mode="static"
    )

    # 3. Preparation: Build retrieval queries
    @pw.udf
    def expand_query(character: str, backstory: str) -> str:
        """
        Generates semantically diverse queries to improve recall.
        Uses character name + key phrases from backstory.
        Output is a space-separated string of tokens for the vector index.
        """
        # 1. Base Query
        base = f"{character} {backstory}"
        
        # 2. Key phrases extraction (simple heuristic)
        import re
        words = re.findall(r'\b[A-Za-z]{5,}\b', backstory) # Long descriptive words
        keywords = " ".join(words[:15]) if words else backstory
        
        # 3. Conflict indicators (to drift search towards sensitive areas)
        conflict_seeds = ""
        if any(w in backstory.lower() for w in ["imprison", "jail", "cell", "prison"]):
            conflict_seeds = "confinement dungeon captive"
        elif any(w in backstory.lower() for w in ["died", "death", "killed", "passed"]):
            conflict_seeds = "deceased burial tomb"

        return f"{base} {keywords} {conflict_seeds}"

    query_table = queries.select(
        query=expand_query(queries.char, queries.content),
        query_id=queries.story_id_numeric,
        character=queries.char,
        backstory=queries.content,
        book_name=queries.book_name
    )
    
    # Handle the 'In Search of the Castaways' capitalization fix using another select if needed, 
    # but let's try the simple version first.

    # 4. Retrieval
    @pw.udf
    def calculate_adaptive_k(backstory: str) -> int:
        """
        Calculates k based on claim complexity.
        More complex backstories need more evidence chunks.
        """
        word_count = len(backstory.split())
        # Base k=10, add 1 for every 20 words, cap at 30
        k = 10 + (word_count // 20)
        return min(k, 30)

    # retrieve_query returns a table with original columns + retrieved chunks + metadata
    retrieved_results = retriever.retrieve(
        query_table, 
        k=calculate_adaptive_k(query_table.backstory)
    )

    # 5. Reranking (Context Optimization)
    @pw.udf
    def rerank_by_contradiction_relevance(chunks: list, metadata: list, character: str, backstory: str) -> tuple:
        """
        Reranks chunks based on potential for contradiction.
        Priority:
        1. Mentions the Character + backstory keywords.
        2. Contains years matching backstory.
        3. Simple heuristic for negation/conflict keywords.
        """
        if not chunks:
            return ([], [])
            
        scores = []
        back_lower = backstory.lower()
        char_lower = character.lower()
        
        for i, chunk in enumerate(chunks):
            chunk_s = str(chunk).lower()
            score = 0
            
            # Entity match bonus
            if char_lower in chunk_s:
                score += 5
            
            # Keyword fragments (simple heuristic)
            for word in back_lower.split()[:10]: # Check first 10 words of backstory
                if len(word) > 4 and word in chunk_s:
                    score += 1
            
            # Temporal overlap detection in chunk
            import re
            years = re.findall(r'\b(17|18|19)\d{2}\b', chunk_s)
            if years:
                score += 2
                
            # Conflict keyword bonus
            conflict_words = ["not", "never", "only", "instead", "imprisoned", "died"]
            for cw in conflict_words:
                if cw in chunk_s:
                    score += 1
            
            scores.append(score)
            
        # Sort indices by score descending
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        
        return (
            [chunks[i] for i in ranked_indices],
            [metadata[i] for i in ranked_indices]
        )

    reranked_results = retrieved_results.select(
        *pw.this,
        reranked_data=rerank_by_contradiction_relevance(
            pw.this.retrieved_chunks, 
            pw.this.retrieved_metadata,
            pw.this.character,
            pw.this.backstory
        )
    )
    
    # Extract tuples
    processed_results = reranked_results.select(
        *pw.this,
        final_chunks=pw.this.reranked_data[0],
        final_metadata=pw.this.reranked_data[1]
    )

    # 6. Preparation of evidence and reasoning context
    @pw.udf
    def build_consistency_prompt(backstory: str, character: str, evidence: str, programmatic_analysis: str) -> str:
        return f"""
        Analyze if the provided Character Backstory is consistent with the Roman-Fleuve (Novel) Narrative.
        
        CHARACTER: {character}
        BACKSTORY CLAIM: {backstory}
        
        --- NOVEL EVIDENCE ---
        {evidence}
        
        --- PROGRAMMATIC ANALYSIS (Timeline & Entities) ---
        {programmatic_analysis}
        
        --- INSTRUCTIONS ---
        1. Identify any explicit or implicit contradictions between the Backstory and the Novel Evidence/Analysis.
        2. Pay special attention to:
           - Temporal Violations (e.g., in two places at once, dead while acting).
           - Location mismatches for specific years.
           - Status changes (e.g., imprisoned in narrative but free in backstory).
        3. NEGATIVE EVIDENCE PROBE: If the novel is silent about a specific claim, explain that silence is NOT a contradiction unless the novel provides evidence for a MUTUALLY EXCLUSIVE state (e.g., 'he was in London' contradicts 'he stayed in Paris').
        4. RATIONALE: Provide a detailed breakdown citing specific chapters or programmatic results.
        
        --- OUTPUT FORMAT ---
        Result: [Consistent / Contradictory]
        Confidence: [High / Medium / Low] (High if explicit evidence, Low if mostly silence)
        Rationale: [Your detailed reasoning]
        """

    @pw.udf
    def combine_evidence(chunks: list, metadata: list, target_book: str) -> str:
        """
        Combines retrieved chunks into formatted evidence string.
        Filters chunks to only include those from the target book.
        """
        if not chunks:
            return "No evidence found."
        
        formatted_evidence = []
        for i, chunk in enumerate(chunks):
            meta = metadata[i] if i < len(metadata) else {}
            
            # Convert Pathway Json object to Python dict
            if hasattr(meta, 'as_dict'):
                meta = meta.as_dict()
            elif hasattr(meta, 'to_dict'):
                meta = meta.to_dict()
            
            chunk_path = str(meta.get("path", "")).lower()
            source_file = str(meta.get("source_file", "")).lower()
            target_book_lower = target_book.lower()
            
            if target_book_lower not in chunk_path and target_book_lower not in source_file:
                continue 
            
            chapter = meta.get("chapter", "Unknown Chapter")
            progress = meta.get("progress_pct", "?")
            
            entry = f"[{chapter} | {progress}%]\n{str(chunk)}"
            formatted_evidence.append(entry)
        
        if not formatted_evidence:
            return f"No evidence found from '{target_book}'."
            
        return "\n---\n".join(formatted_evidence)

    evidence_table = processed_results.select(
        *pw.this,
        evidence=combine_evidence(pw.this.final_chunks, pw.this.final_metadata, pw.this.book_name)
    )

    # 5. Programmatic Reasoning (Hybrid Layer)
    @pw.udf
    def perform_programmatic_reasoning(backstory: str, chunks: list, metadata: list, target_book: str) -> str:
        """
        Executes deterministic consistency checks before LLM judging.
        Returns a JSON string of detected conflicts.
        """
        # Filter chunks for this book first (same logic as combine_evidence)
        valid_chunks = []
        valid_meta = []
        target_book_lower = target_book.lower()
        
        for i, chunk in enumerate(chunks):
            meta = metadata[i] if i < len(metadata) else {}
            if hasattr(meta, 'as_dict'): meta = meta.as_dict()
            elif hasattr(meta, 'to_dict'): meta = meta.to_dict()
            elif not isinstance(meta, dict):
                try: meta = dict(meta)
                except: meta = {}
            
            path = str(meta.get("path", "")).lower()
            source = str(meta.get("source_file", "")).lower()
            if target_book_lower in path or target_book_lower in source:
                valid_chunks.append(str(chunk))
                valid_meta.append(meta)

        if not valid_chunks:
            return json.dumps({"conflicts": [], "summary": "No specific evidence for cross-referencing."})

        # Initialize Reasoning Engine
        tracker = EntityStateTracker()
        validator = TimelineValidator()
        rules = ConstraintRules()

        # Extract States
        narrative_states = tracker.get_states_from_chunks(valid_chunks, valid_meta)
        backstory_claims = tracker.parse_backstory_claims(backstory)

        # Run Checks
        conflicts = []
        conflicts.extend(validator.validate_location_consistency(backstory_claims, narrative_states))
        conflicts.extend(rules.check_imprisonment_constraint(backstory_claims, narrative_states))
        conflicts.extend(rules.check_death_constraint(backstory_claims, narrative_states))

        return json.dumps({
            "conflicts": conflicts,
            "summary": f"Detected {len(conflicts)} potential factual conflicts." if conflicts else "No programmatic conflicts detected."
        })

    reasoning_table = evidence_table.select(
        *pw.this,
        programmatic_results=perform_programmatic_reasoning(
            pw.this.backstory,
            pw.this.final_chunks,
            pw.this.final_metadata,
            pw.this.book_name
        )
    )

    # 6. Consistency Judgment
    # Updated build_consistency_prompt could take programmatic results
    prompt_table = reasoning_table.select(
        *pw.this,
        prompt=build_consistency_prompt(
            backstory=pw.this.backstory,
            character=pw.this.character,
            evidence=pw.this.evidence,
            programmatic_analysis=pw.this.programmatic_results
        )
    )

    # Run LLM (Dual-Pass + Determinism)
    # 6. Judicial Reasoning
    final_reasoning = judge.judge(prompt_table)

    @pw.udf
    def extract_judgment_and_confidence(llm_response: str) -> tuple:
        """
        Parses LLM response for Result, Confidence, and Rationale.
        Handles both our new format and the project's legacy JSON format if fallback occurs.
        """
        response = llm_response.lower()
        
        # 1. Result parsing
        res = "Consistent"
        if "contradictory" in response or '"label": 0' in response:
            res = "Contradictory"
            
        # 2. Confidence parsing
        conf = "Medium"
        if "confidence: high" in response or "high confidence" in response:
            conf = "High"
        elif "confidence: low" in response or "low confidence" in response:
            conf = "Low"
            
        # 3. Rationale parsing
        rat = llm_response
        if "rationale:" in response:
            # Case insensitive split
            try:
                idx = response.find("rationale:")
                rat = llm_response[idx+len("rationale:"):].strip()
            except:
                pass
        elif '"rationale":' in response:
            try:
                # Handle legacy JSON fallback
                clean_json = llm_response
                if "```json" in clean_json: clean_json = clean_json.split("```json")[1].split("```")[0]
                data = json.loads(clean_json)
                rat = data.get("rationale", llm_response)
            except:
                pass
                
        return res, conf, rat

    judged_table = final_reasoning.select(
        *pw.this,
        judgment_data=extract_judgment_and_confidence(pw.this.result)
    ).select(
        *pw.this,
        judgment=pw.this.judgment_data[0],
        confidence=pw.this.judgment_data[1],
        rationale=pw.this.judgment_data[2]
    )

    # 7. Output Generation
    @pw.udf
    def parse_label(judgment: str) -> int:
        return 1 if judgment.lower() == "contradictory" else 0

    output_table = judged_table.select(
        Story_ID=pw.this.query_id,
        Prediction=parse_label(pw.this.judgment),
        Rationale=pw.this.rationale,
        Confidence=pw.this.confidence
    )

    # Export to CSV
    pw.io.csv.write(output_table, OUTPUT_FILE)

    # Pathway runs everything as a compute graph
    pw.run()
    
    # Post-processing: Clean up Pathway's internal columns (time, diff)
    try:
        import csv
        cleaned_rows = []
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                print("[WARNING] results.csv is empty.")
                return

            col_map = {col: i for i, col in enumerate(header)}
            
            for row in reader:
                if not row: continue
                try:
                    # Robust column mapping
                    idx_id = col_map.get("Story ID", col_map.get("Story_ID", 0))
                    idx_pred = col_map.get("Prediction", 1)
                    idx_rat = col_map.get("Rationale", 2)
                    idx_conf = col_map.get("Confidence", 3)
                    
                    story_id = row[idx_id]
                    pred = row[idx_pred]
                    rat = row[idx_rat]
                    conf = row[idx_conf]
                    cleaned_rows.append([story_id, pred, rat, conf])
                except (IndexError, KeyError):
                    continue
        
        if cleaned_rows:
            df = pd.DataFrame(cleaned_rows, columns=["Story ID", "Prediction", "Rationale", "Confidence"])
            df.to_csv(OUTPUT_FILE, index=False)
            print(f"[INFO] Cleaned CSV output: {len(df)} predictions written to {OUTPUT_FILE}")
        else:
            print("[WARNING] No valid rows found in CSV.")
    except Exception as e:
        print(f"[WARNING] Could not clean CSV: {e}")

if __name__ == "__main__":
    main()
