import re
import os

def split_by_chapter(path):
    with open(path, 'rb') as f:
        text = f.read().decode("utf-8")
    
    chapter_pattern = r'(?m)^(?:CHAPTER|Chapter|PART|Part|BOOK|Book)\s+(?:[IVXLCDM\d]+|[A-Z]+).*$'
    matches = list(re.finditer(chapter_pattern, text))
    
    print(f"File: {path}")
    print(f"Total Length: {len(text)}")
    print(f"Chapter Matches: {len(matches)}")
    
    if matches:
        for i, m in enumerate(matches[:3]):
            print(f"  Match {i}: {m.group(0).strip()}")
    else:
        print("  NO MATCHES - Whole file will be one chunk!")

if __name__ == "__main__":
    split_by_chapter("Dataset/Books/In search of the castaways.txt")
    split_by_chapter("Dataset/Books/The Count of Monte Cristo.txt")
