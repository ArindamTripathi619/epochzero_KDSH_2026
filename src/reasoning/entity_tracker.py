import spacy
import os
import pickle
import logging
from typing import Set, List, Dict

logger = logging.getLogger(__name__)

class GlobalEntityManager:
    def __init__(self, books_dir: str):
        self.books_dir = books_dir
        self.nlp = spacy.load("en_core_web_sm", disable=["parser", "attribute_ruler", "lemmatizer"])
        self.entities = set()
        self.cache_file = ".entities_cache.pkl"
        
    def build_index(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "rb") as f:
                self.entities = pickle.load(f)
            logger.info(f"Loaded {len(self.entities)} entities from cache.")
            return

        logger.info("Building Global Entity Index (this may take a minute)...")
        for filename in os.listdir(self.books_dir):
            if filename.endswith(".txt"):
                path = os.path.join(self.books_dir, filename)
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                    chunk_size = 50000
                    for i in range(0, len(text), chunk_size):
                        doc = self.nlp(text[i:i+chunk_size])
                        for ent in doc.ents:
                            if ent.label_ in ["PERSON", "LOC", "FAC", "GPE"]:
                                self.entities.add(ent.text.strip().lower())
        
        with open(self.cache_file, "wb") as f:
            pickle.dump(self.entities, f)

    def check_hallucination(self, backstory: str, character: str = "") -> List[str]:
        doc = self.nlp(backstory)
        # Only Title Case entities are likely true names/places
        bs_ents = [ent.text.strip() for ent in doc.ents if ent.label_ in ["PERSON", "LOC", "GPE", "FAC", "ORG"]]
        unknown = []
        char_parts = character.lower().split()
        
        for ent in bs_ents:
            ent_lower = ent.lower()
            # Ignore self-mentions or parts of character name
            if any(part in ent_lower for part in char_parts if len(part) > 2):
                continue
            # Ignore purely lowercase or single characters
            if not any(c.isupper() for c in ent):
                continue
            # Check length and presence in global set
            if len(ent) > 4 and ent_lower not in self.entities:
                # Basic check for common adjectives flagged as place
                if ent_lower not in ["hispan", "french", "british", "australian", "spanish", "political"]:
                    unknown.append(ent)
        return unknown

class EntityStateTracker:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")
        
    def get_states_from_chunks(self, chunks: list, metadata: list) -> List[Dict]:
        states = []
        for i, chunk in enumerate(chunks):
            text = str(chunk)
            # Basic years and locations extraction
            import re
            years = [int(y) for y in re.findall(r'\b(17|18|19)\d{2}\b', text)]
            states.append({
                "content_snippet": text[:500],
                "years": years,
                "chapter": metadata[i].get("chapter", "Unknown") if i < len(metadata) else "Unknown"
            })
        return states

    def parse_backstory_claims(self, backstory: str) -> Dict:
        import re
        years = [int(y) for y in re.findall(r'\b(17|18|19)\d{2}\b', backstory)]
        doc = self.nlp(backstory)
        locations = [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]
        return {"years": years, "locations": locations}

    def extract_basic_entities(self, text: str) -> Dict:
        doc = self.nlp(text)
        ents = {"PERSON": [], "GPE": [], "LOC": []}
        for ent in doc.ents:
            if ent.label_ in ents:
                ents[ent.label_].append(ent.text)
        return ents
