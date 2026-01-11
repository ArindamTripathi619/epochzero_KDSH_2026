import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from src.reasoning.entity_tracker import EntityStateTracker
from src.reasoning.timeline_validator import TimelineValidator
from src.reasoning.constraint_rules import ConstraintRules

def test_location_conflict():
    print("Testing Location Conflict Detection...")
    tracker = EntityStateTracker()
    validator = TimelineValidator()
    
    backstory = "In 1815, Edmond Dantes was celebrating in Paris."
    narrative_chunks = [
        "In 1815, Dantes was thrown into the dungeon of the Chateau d'If."
    ]
    metadatas = [{"chapter": "Chapter 8", "progress_pct": 0.1, "path": "monte_cristo.txt"}]
    
    backstory_claims = tracker.parse_backstory_claims(backstory)
    narrative_states = tracker.get_states_from_chunks(narrative_chunks, metadatas)
    
    print(f"Backstory Claims: {backstory_claims}")
    print(f"Narrative States: {narrative_states}")
    
    conflicts = validator.validate_location_consistency(backstory_claims, narrative_states)
    
    print(f"Detected Conflicts: {json.dumps(conflicts, indent=2)}")
    assert len(conflicts) > 0
    assert conflicts[0]["type"] == "Location Conflict"
    print("SUCCESS: Location conflict detected.")

def test_death_conflict():
    print("\nTesting Death Constraint Detection...")
    tracker = EntityStateTracker()
    rules = ConstraintRules()
    
    backstory = "In 1830, the character visited the grave of his father."
    # Let's say backstory claims character was active in 1845
    backstory_extended = "After his father's death in 1830, he lived in London until 1845."
    
    narrative_chunks = [
        "The poor man died in the year 1820, leaving no heirs."
    ]
    metadatas = [{"chapter": "Postscript", "progress_pct": 0.9, "path": "story.txt"}]
    
    backstory_claims = tracker.parse_backstory_claims(backstory_extended)
    narrative_states = tracker.get_states_from_chunks(narrative_chunks, metadatas)
    
    conflicts = rules.check_death_constraint(backstory_claims, narrative_states)
    
    print(f"Detected Conflicts: {json.dumps(conflicts, indent=2)}")
    assert len(conflicts) > 0
    assert conflicts[0]["type"] == "Post-Mortem Activity"
    print("SUCCESS: Post-mortem activity detected.")

if __name__ == "__main__":
    try:
        test_location_conflict()
        test_death_conflict()
        print("\nALL STRESS TESTS PASSED.")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
