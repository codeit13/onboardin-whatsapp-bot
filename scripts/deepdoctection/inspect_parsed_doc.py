import pickle
from pathlib import Path

# IMPORTANT: import class definitions used during pickling
from layout_aware_pdf_parser import ParsedDoc, Chunk

PKL_PATH = Path("./parsed_output/Attendance.pkl")

with open(PKL_PATH, "rb") as f:
    doc = pickle.load(f)

print("\n" + "=" * 100)
print("DOCUMENT METADATA")
print("=" * 100)
print("Doc ID     :", doc.doc_id)
print("Doc Path   :", doc.doc_path)
print("Total Chunks:", len(doc.chunks))
# print("Total Tables:", len(doc.tables))


# ------------------------------------------------------------------
# TEXT CHUNKS (FULL DISPLAY)
# ------------------------------------------------------------------
print("\n" + "=" * 100)
print("LAYOUT-AWARE TEXT CHUNKS (FULL CONTENT)")
print("=" * 100)

for idx, ch in enumerate(doc.chunks, start=1):
    print(f"\n########## CHUNK {idx} ##########")
    print("Pages      :", sorted(set(ch.page_numbers)))
    print("Titles     :", ch.titles)
    print("Categories :", ch.categories)
    print("\nTEXT:\n")
    print(ch.text.strip())
    print("\n" + "#" * 80)