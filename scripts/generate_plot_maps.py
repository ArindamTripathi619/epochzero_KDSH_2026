"""
generate_plot_maps.py — V5.0 Hierarchical Plot Map Generator

Strategy: Instead of fragile chapter-splitting regex, use fixed-length
windows to guarantee FULL novel coverage, then hierarchically summarize.

Architecture:
  1. Slice the entire book into fixed windows (~10K chars each)
  2. Summarize each window into 2 sentences (Pass 1)
  3. If >15 windows: group summaries into clusters of 8, summarize each cluster (Pass 2)
  4. Synthesize all summaries into a structured 600-word Plot Map (Final Pass)
"""

import os
import requests
import json
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")
DUMMY_KEY = os.environ.get("OPENAI_API_KEY", "sk-dummy")
BOOKS_DIR = "Dataset/Books/"
OUTPUT_DIR = "Dataset/PlotMaps/"

WINDOW_SIZE = 10000  # characters per window
OVERLAP = 500        # small overlap to avoid cutting mid-sentence


def llm_call(prompt: str, model: str = "groq-llama-small", max_tokens: int = 600, timeout: int = 45) -> str:
    """Single LLM call with retry logic."""
    import time
    for attempt in range(5):
        try:
            res = requests.post(
                f"{API_BASE}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": max_tokens,
                },
                headers={"Authorization": f"Bearer {DUMMY_KEY}"},
                timeout=timeout,
            )
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"].strip()
            elif res.status_code == 429:
                wait = (2 ** attempt) + 3
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  API error {res.status_code}: {res.text[:200]}")
                time.sleep(2)
        except Exception as e:
            print(f"  Request error: {e}")
            time.sleep(2)
    return ""


def slice_into_windows(text: str) -> list[str]:
    """Slice text into fixed-length windows with small overlap."""
    windows = []
    start = 0
    while start < len(text):
        end = start + WINDOW_SIZE
        # Try to break at a sentence boundary (look for ". " near the end)
        if end < len(text):
            # Search backwards from `end` for a sentence-ending period
            cutoff = text.rfind(". ", max(start, end - 300), end)
            if cutoff > start:
                end = cutoff + 1  # include the period
        window = text[start:end].strip()
        if len(window) > 200:  # skip tiny trailing fragments
            windows.append(window)
        start = end - OVERLAP  # overlap with next window
    return windows


def summarize_window(window: str, window_idx: int, total: int) -> str:
    """Summarize a single text window into 2-3 concise sentences."""
    prompt = f"""Summarize this passage from a novel in exactly 2-3 concise sentences.
Focus on: key events, character actions, important revelations, and timeline markers (dates, locations).

Passage (section {window_idx+1} of {total}):
{window[:8000]}"""
    return llm_call(prompt, model="groq-llama-small", max_tokens=200)


def summarize_cluster(summaries: list[str], cluster_idx: int) -> str:
    """Summarize a cluster of individual summaries into a paragraph."""
    combined = "\n".join(f"- {s}" for s in summaries)
    prompt = f"""These are sequential summaries from a novel. Combine them into a single coherent paragraph (100-150 words) that preserves key events, character names, dates, and locations.

Summaries (Group {cluster_idx+1}):
{combined}"""
    return llm_call(prompt, model="groq-llama-small", max_tokens=300)


def synthesize_plot_map(summaries: list[str], book_title: str) -> str:
    """Final synthesis: produce a structured Plot Map with ONLY factual content."""
    combined = "\n".join(f"[Section {i+1}] {s}" for i, s in enumerate(summaries))
    prompt = f"""You are a literary analyst. Given these sequential summaries of the novel "{book_title}", 
synthesize a comprehensive, structured Plot Map.

The Plot Map MUST include ALL of the following sections:

1. **Key Characters and Arcs**: List EVERY major character with a 1-sentence arc description. Include ALL characters, not just the protagonist.
2. **Timeline Anchors**: ALL specific years, dates, and locations mentioned throughout the ENTIRE novel.
3. **Central Causal Relationships**: How key events cause later events — cover relationships from beginning, middle, AND end.
4. **Plot Sequence**: A chronological summary covering the ENTIRE novel from the very first chapter to the final resolution/ending. You MUST describe how the novel ends.

CRITICAL RULES:
- Cover the COMPLETE story — beginning, middle, AND ending. Do NOT stop partway through.
- Include ONLY factual plot information. NO literary analysis, no "masterpiece" commentary, no conclusions about themes.
- Every sentence must contain a character name, event, date, or location.
- Do NOT write any concluding paragraphs or meta-commentary about the novel's significance.

Sequential Summaries:
{combined[:14000]}"""
    return llm_call(prompt, model="groq-scout", max_tokens=2000, timeout=90)


def process_book(filename: str):
    book_title = filename.replace(".txt", "")
    print(f"\n{'='*60}")
    print(f"Processing: {book_title}")
    print(f"{'='*60}")

    path = os.path.join(BOOKS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"  Book length: {len(content):,} characters")

    # Step 1: Slice into windows
    windows = slice_into_windows(content)
    print(f"  Windows: {len(windows)} (each ~{WINDOW_SIZE:,} chars)")

    # Step 2: Summarize each window (Pass 1)
    window_summaries = []
    for i, window in enumerate(tqdm(windows, desc="  Pass 1 — Window summaries")):
        summary = summarize_window(window, i, len(windows))
        if summary:
            window_summaries.append(summary)

    print(f"  Valid window summaries: {len(window_summaries)}")

    if not window_summaries:
        print(f"  ERROR: No summaries generated for {book_title}. Skipping.")
        return

    # Step 3: Hierarchical clustering (Pass 2) — only if many windows
    final_summaries = window_summaries
    if len(window_summaries) > 15:
        print(f"  Pass 2 — Clustering {len(window_summaries)} summaries into groups of 8...")
        cluster_size = 8
        clustered = []
        for i in range(0, len(window_summaries), cluster_size):
            cluster = window_summaries[i : i + cluster_size]
            cluster_summary = summarize_cluster(cluster, i // cluster_size)
            if cluster_summary:
                clustered.append(cluster_summary)
        print(f"  Clustered summaries: {len(clustered)}")
        final_summaries = clustered

    # Step 4: Final synthesis (Pass 3)
    print(f"  Pass 3 — Synthesizing final Plot Map from {len(final_summaries)} summaries...")
    plot_map = synthesize_plot_map(final_summaries, book_title)

    if not plot_map or len(plot_map) < 100:
        print(f"  WARNING: Plot map too short ({len(plot_map)} chars). Retrying with different model...")
        plot_map = synthesize_plot_map(final_summaries, book_title)

    # Save
    output_path = os.path.join(OUTPUT_DIR, f"{book_title}_plot_map.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(plot_map)
    print(f"  ✓ Saved Plot Map ({len(plot_map):,} chars) → {output_path}")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    books = [b for b in os.listdir(BOOKS_DIR) if b.endswith(".txt")]
    print(f"Found {len(books)} books: {books}")
    for book in books:
        process_book(book)
    print("\n✓ All plot maps generated.")
