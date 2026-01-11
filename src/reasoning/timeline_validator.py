import networkx as nx
from typing import List, Dict, Tuple

class TimelineValidator:
    """
    Builds a temporal constraint graph and validates backstory compatibility.
    Focuses on location consistency (a character cannot be in two places at once).
    """
    
    def validate_location_consistency(self, backstory_claims: Dict, narrative_states: List[Dict]) -> List[Dict]:
        """
        Detects if a character is in two places at once.
        Example: Backstory says Paris in 1815, Narrative says Chateau d'If in 1815.
        """
        violations = []
        b_years = backstory_claims.get("years", [])
        b_locs = backstory_claims.get("locations", [])
        b_persons = backstory_claims.get("persons", [])

        if not b_years or not b_locs:
            return []

        for state in narrative_states:
            n_years = state.get("years", [])
            n_locs = state.get("locations", [])
            n_persons = state.get("persons", [])
            
            # Find year overlap
            common_years = set(b_years) & set(n_years)
            if common_years:
                # Fuzzy person matching: Check if any backstory person is a substring 
                # of a narrative person or vice-versa
                common_persons = []
                for bp in b_persons:
                    for np in n_persons:
                        if bp.lower() in np.lower() or np.lower() in bp.lower():
                            common_persons.append(bp)
                            break
                
                if common_persons:
                    # If they share a person and a year, check for location mismatch.
                    # We improve this by checking if backlight location is explicitly 
                    # NOT in the narrative context snippet.
                    snippet = state.get("content_snippet", "").lower()
                    for bl in b_locs:
                        # If the narrative location is explicitly mentioned as something else
                        # OR if the narrative context doesn't mention the backstory location
                        # but mentions some other location.
                        if bl.lower() not in snippet:
                            # Potential location conflict
                            violations.append({
                                "type": "Location Conflict",
                                "year": list(common_years)[0],
                                "backstory_location": bl,
                                "narrative_locations": n_locs,
                                "persons": common_persons,
                                "chapter": state["chapter"]
                            })
            
        return violations

    def build_narrative_graph(self, narrative_states: List[Dict]) -> nx.DiGraph:
        """
        Builds a DAG of events based on progress percentage.
        """
        G = nx.DiGraph()
        
        last_node = None
        for i, state in enumerate(narrative_states):
            node_id = f"state_{i}"
            G.add_node(node_id, **state)
            if last_node:
                G.add_edge(last_node, node_id)
            last_node = node_id
            
        return G
