import pathway as pw
from typing import Optional

def test():
    t = pw.debug.table_from_rows(
        rows=[("q1", "f1")],
        schema=pw.schema_from_types(query=str, metadata_filter=str)
    )
    
    # Try to cast metadata_filter to Optional[str]
    t2 = t.select(
        query=pw.this.query,
        metadata_filter=pw.cast(Optional[str], pw.this.metadata_filter)
    )
    
    print("Schema of t2:")
    print(t2.schema)
    
    try:
        # pw.cast(str, ...)
        t3 = t.select(
            query=pw.this.query,
            metadata_filter=pw.cast(str, pw.this.metadata_filter)
        )
        print("Casting to str worked")
    except Exception as e:
        print(f"Casting to str failed: {e}")

if __name__ == "__main__":
    test()
