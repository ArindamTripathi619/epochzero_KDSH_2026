import spacy
import json
from typing import List, Dict, Tuple

class EntityStateTracker:
    """
    Tracks character states, locations, and actions across a narrative timeline.
    Uses spaCy for basic entity detection and can be extended with LLM for 
    refined relation extraction.
    """
    
    def __init__(self, model_name="en_core_web_sm"):
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            # Fallback if model not found (though we just installed it)
            self.nlp = None
            print(f"Warning: spaCy model {model_name} not found.")

    def extract_basic_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract People and Locations from text with fallback heuristics."""
        entities = {"PERSON": [], "GPE": [], "LOC": []}
        
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in entities:
                    if ent.text not in entities[ent.label_]:
                        entities[ent.label_].append(ent.text)
        
        # KEYWORD FALLBACKS (Important for narrative places like 'Chateau d'If')
        # This helps when spaCy misses custom entities
        location_keywords = ["Chateau", "Paris", "London", "Marseilles", "Rome", "Island", "Dungeon"]
        for kw in location_keywords:
            if kw.lower() in text.lower() and kw not in entities["LOC"] and kw not in entities["GPE"]:
                entities["LOC"].append(kw)
        
        # Simple person detection heuristic if spaCy misses it (e.g. capitalized single names)
        # (Optional, but useful for 'Dantes')
        import re
        names = re.findall(r'\b[A-Z][a-z]+\b', text)
        for name in names:
            if name not in entities["PERSON"] and name not in location_keywords:
                # Basic check to avoid common starts of sentences
                if name not in ["The", "He", "She", "It", "They", "But", "In", "On", "At"]:
                    entities["PERSON"].append(name)

        return entities

    def extract_years(self, text: str) -> List[int]:
        """Extract years (4 digits) from text."""
        import re
        years = re.findall(r'\b(17\d{2}|18\d{2}|19\d{2})\b', text)
        return sorted(list(set([int(y) for y in years])))

    def get_states_from_chunks(self, chunks: List[str], metadatas: List[Dict]) -> List[Dict]:
        """
        Processes chunks and returns a simplified 'state' representation.
        """
        states = []
        for i, chunk in enumerate(chunks):
            metadata = metadatas[i]
            ents = self.extract_basic_entities(chunk)
            years = self.extract_years(chunk)
            
            states.append({
                "progress_pct": metadata.get("progress_pct", 0.0),
                "chapter": metadata.get("chapter", "Unknown"),
                "persons": ents["PERSON"],
                "locations": list(set(ents["GPE"] + ents["LOC"])),
                "years": years,
                "content_snippet": chunk[:500] # Increased context
            })
            
        states.sort(key=lambda x: x["progress_pct"])
        return states

    def parse_backstory_claims(self, backstory: str) -> Dict:
        """
        Extracts key entities, locations, and years from the backstory.
        """
        ents = self.extract_basic_entities(backstory)
        years = self.extract_years(backstory)
        return {
            "persons": ents["PERSON"],
            "locations": list(set(ents["GPE"] + ents["LOC"])),
            "years": years,
            "content": backstory
        }
