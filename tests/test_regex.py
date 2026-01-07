import re
import unittest

def get_chunks(text):
    # This regex must match the one in src/pathway_pipeline/retrieval.py
    chapter_pattern = r'(?m)^(?:CHAPTER|Chapter|PART|Part|BOOK|Book)\s+(?:[IVXLCDM\d]+|[A-Z]+).*$'
    
    matches = list(re.finditer(chapter_pattern, text))
    if not matches:
        return ["Full Text"]
    
    chunks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        chapter_title = match.group(0).strip()
        chunks.append(chapter_title)
        
    if matches[0].start() > 0:
        chunks.insert(0, "Preamble")
        
    return chunks

class TestChapterRegex(unittest.TestCase):
    def test_standard_chapters(self):
        text = """
The Beginning.

CHAPTER I
The Start

CHAPTER II
The Middle
"""
        chunks = get_chunks(text)
        self.assertIn("CHAPTER I", chunks)
        self.assertIn("CHAPTER II", chunks)
        self.assertIn("Preamble", chunks)

    def test_part_book(self):
        text = """
PART I
The Beginning

BOOK II
The Sequel
"""
        chunks = get_chunks(text)
        self.assertIn("PART I", chunks)
        self.assertIn("BOOK II", chunks)

    def test_mixed_case(self):
        text = """
Chapter 1
Start

Part A
Next
"""
        chunks = get_chunks(text)
        self.assertIn("Chapter 1", chunks)
        self.assertIn("Part A", chunks)

if __name__ == '__main__':
    unittest.main()
