from typing import List, Dict

class ConstraintRules:
    """
    Defines implicit narrative constraints and rules for consistency.
    """
    
    @staticmethod
    def check_imprisonment_constraint(backstory_claims: Dict, narrative_states: List[Dict]) -> List[Dict]:
        """
        Rule: If narrative says a character is imprisoned, they cannot travel in the backstory
        covering the same period.
        """
        violations = []
        imprisonment_keywords = ["imprisoned", "prison", "dungeon", "jail", "captive", "cell", "d'if"]
        
        b_years = backstory_claims.get("years", [])
        b_locs = backstory_claims.get("locations", [])
        
        for state in narrative_states:
            snippet = state.get("content_snippet", "").lower()
            if any(k in snippet for k in imprisonment_keywords):
                # Narrative says character is in prison.
                n_years = state.get("years", [])
                common_years = set(b_years) & set(n_years)
                
                # If backstory claims they were in an external location during a prison year
                if common_years and b_locs:
                    for loc in b_locs:
                        # Simple heuristic: if 'jail'/'prison' is in the narrative but not the backstory location
                        if loc.lower() not in ["prison", "jail", "cell", "dungeon"]:
                            violations.append({
                                "type": "Imprisonment Violation",
                                "year": list(common_years)[0],
                                "backstory_location": loc,
                                "narrative_context": "Character was imprisoned at this time.",
                                "chapter": state["chapter"]
                            })
        
        return violations

    @staticmethod
    def check_death_constraint(backstory_claims: Dict, narrative_states: List[Dict]) -> List[Dict]:
        """
        Rule: A character cannot perform actions after they have died in the narrative.
        """
        violations = []
        death_keywords = ["died", "deceased", "grave", "buried", "death", "killed", "guillotine"]
        
        b_years = backstory_claims.get("years", [])
        
        for state in narrative_states:
            snippet = state.get("content_snippet", "").lower()
            if any(k in snippet for k in death_keywords):
                n_years = state.get("years", [])
                if n_years:
                    death_year = max(n_years)
                    # If backstory mentions ANY year after this death year
                    post_death_years = [y for y in b_years if y > death_year]
                    if post_death_years:
                        violations.append({
                            "type": "Post-Mortem Activity",
                            "death_year": death_year,
                            "backstory_years": post_death_years,
                            "narrative_context": "Character died in or before this year.",
                            "chapter": state["chapter"]
                        })
        
        return violations
