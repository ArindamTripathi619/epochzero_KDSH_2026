import logging
import torch
import torch.nn.functional as F
import spacy
import re
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

# Global instances for model sharing across Pathway workers
_model_instance = None
_bi_encoder_instance = None
_spacy_instance = None
_reranker_instance = None

def get_models():
    global _model_instance, _bi_encoder_instance, _spacy_instance, _reranker_instance
    if _model_instance is None:
        from sentence_transformers import CrossEncoder
        _model_instance = CrossEncoder('cross-encoder/nli-deberta-v3-small')
    if _bi_encoder_instance is None:
        from sentence_transformers import SentenceTransformer
        _bi_encoder_instance = SentenceTransformer('all-MiniLM-L6-v2')
    if _spacy_instance is None:
        _spacy_instance = spacy.load("en_core_web_sm")
    if _reranker_instance is None:
        from sentence_transformers import CrossEncoder
        _reranker_instance = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    return _model_instance, _bi_encoder_instance, _spacy_instance, _reranker_instance

def get_nlp():
    _, _, nlp, _ = get_models()
    return nlp

def extract_years(text: str) -> List[int]:
    return [int(y) for y in re.findall(r'\b(17\d{2}|18\d{2}|19\d{2})\b', text)]

def check_temporal_clash(claim: str, evidence: str) -> bool:
    """Returns True if the claim and evidence contain different, non-overlapping years."""
    c_years = extract_years(claim)
    e_years = extract_years(evidence)
    if c_years and e_years:
        return not any(y in e_years for y in c_years)
    return False

def evaluate_backstory_nli(backstory: str, retrieved_chunks: list[dict]) -> tuple[int, str, list[dict]]:
    """
    Evaluates a backstory against chunks using NLI and temporal checks.
    Returns (label, rationale) where label: 0 (contradict), 1 (consistent).
    """
    cross_enc, bi_enc, nlp, reranker = get_models()
    
    # 1. Chunk Reranking
    if len(retrieved_chunks) > 12:
        pairs = [(backstory, c.get("text", "")) for c in retrieved_chunks]
        scores = reranker.predict(pairs)
        ranked = sorted(zip(retrieved_chunks, scores), key=lambda x: x[1], reverse=True)
        retrieved_chunks = [x[0] for x in ranked[:12]]

    # 2. Break backstory into atomic claims
    doc_bs = nlp(backstory)
    claims = [sent.text.strip() for sent in doc_bs.sents if len(sent.text.strip()) > 8]
    if not claims: claims = [backstory]
        
    all_evidence_sentences = []
    sentence_to_source = {}
    
    for chunk in retrieved_chunks:
        c_text = chunk.get("text", "")
        c_source = chunk.get("chapter", "Book")
        c_doc = nlp(c_text)
        for sent in c_doc.sents:
            s_text = sent.text.strip()
            if len(s_text) > 12:
                all_evidence_sentences.append(s_text)
                sentence_to_source[s_text] = c_source

    if not all_evidence_sentences:
         return 1, "Consistent (No evidence found)", retrieved_chunks

    from sentence_transformers import util
    ev_embeddings = bi_enc.encode(all_evidence_sentences, convert_to_tensor=True)
    
    strong_contradictions = []  
    moderate_contradictions = []  
    
    for claim in claims:
        claim_emb = bi_enc.encode(claim, convert_to_tensor=True)
        hits = util.semantic_search(claim_emb, ev_embeddings, top_k=8)[0]
        relevant_candidates = [(all_evidence_sentences[hit['corpus_id']], hit['score']) for hit in hits if hit['score'] > 0.20]
        
        if not relevant_candidates: continue
            
        pairs = [(c[0], claim) for c in relevant_candidates]
        logits = cross_enc.predict(pairs)
        probs = F.softmax(torch.tensor(logits), dim=1)
        
        max_contra = 0.0
        min_entail_at_max_contra = 1.0  
        max_entail = 0.0
        voter_source = "None"
        voter_evidence = "None"
        
        for i, (ev_sent, sim_score) in enumerate(relevant_candidates):
            p = probs[i]
            contra, entail, neutral = p[0].item(), p[1].item(), p[2].item()
            
            if contra > max_contra:
                max_contra = contra
                min_entail_at_max_contra = entail
                voter_source = sentence_to_source.get(ev_sent, "Book")
                voter_evidence = ev_sent
                
            if entail > max_entail:
                max_entail = entail

        # Entailment Override
        if max_entail > 0.40:
             continue

        temporal_clash = check_temporal_clash(claim, voter_evidence)

        # Original strict thresholds
        if (max_contra > 0.90 and min_entail_at_max_contra < 0.12) or (temporal_clash and max_contra > 0.65):
            reason = f"Claim: '{claim}' -> CONTRADICTED BY {voter_source}: '{voter_evidence}'"
            if temporal_clash: reason += " [TEMPORAL CLASH]"
            strong_contradictions.append(reason)
        elif max_contra > 0.85 and max_contra > (max_entail + 0.45):
            reason = f"Claim: '{claim}' -> WEAK CONTRA BY {voter_source}: '{voter_evidence}'"
            moderate_contradictions.append(reason)

    # Final verdict
    if len(strong_contradictions) >= 1:
        return 0, " | ".join(strong_contradictions[:2]), retrieved_chunks
    elif len(moderate_contradictions) >= 2:
        return 0, " | ".join(moderate_contradictions[:2]), retrieved_chunks
    
    return 1, "Consistent", retrieved_chunks
