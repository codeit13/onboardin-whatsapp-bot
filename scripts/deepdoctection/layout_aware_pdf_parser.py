import os
import pickle
import logging
from typing import List, Dict, Tuple
import torch

import deepdoctection as dd
from bs4 import BeautifulSoup

import torch
# torch.device("cpu")

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------
# Analyzer Initialization
# ---------------------------
def init_analyzer(doc_lang: str = "en"):
    """
    Initialize DeepDocDetection analyzer.
    """
    logger.info("Initializing DeepDocDetection analyzer")
    analyzer = dd.get_dd_analyzer()
    return analyzer


# ---------------------------
# Document Loading
# ---------------------------
def load_doc(path: str, analyzer):
    """
    Load and analyze PDF document.
    """
    logger.info(f"Loading document: {path}")
    df = analyzer.analyze(path=path)
    df.reset_state()
    return iter(df)

def table_html_to_semantic_text(table_html: str) -> str:
    """
    Convert HTML table to embedding-friendly semantic text.
    """
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")

    lines = []
    for row in rows:
        cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
        if cells:
            lines.append(" | ".join(cells))

    if not lines:
        return ""

    return "\n".join(lines)

# ---------------------------
# Page & Block Parsing
# ---------------------------
def get_block_data(block) -> Dict:
    """
    Extract relevant metadata from a block.
    """
    block_data = {
        "document_id": str(block[0]),
        "image_id": str(block[1]),
        "page_number": str(block[2]),
        "annotation_id": str(block[3]),
        "reading_order": str(block[4]),
        "category_name": block[-2].name,
        "text": str(block[-1])
    }
    return block_data


def get_page_data(page) -> List[Dict]:
    """
    Extract all parsed blocks from a page.
    """
    all_blocks = []
    try:
        for block in page.chunks:
            all_blocks.append(get_block_data(block))
    except Exception as e:
        logger.exception(f"Error parsing page {page.page_number}: {e}")
    return all_blocks


# ---------------------------
# Document Traversal
# ---------------------------
def fetch_data_from_doc(doc):
    """
    Fetch parsed text blocks and inject tables as semantic text blocks.
    """
    continuous_chunks = []
    page_wise_chunks = []

    try:
        for page in doc:
            page_chunks = get_page_data(page)

            # Inject tables as text blocks
            if page.tables:
                for table in page.tables:
                    table_text = table_html_to_semantic_text(table.html)
                    if table_text.strip():
                        table_block = {
                            "document_id": page_chunks[0]["document_id"] if page_chunks else "",
                            "image_id": "",
                            "page_number": str(page.page_number),
                            "annotation_id": "table",
                            "reading_order": "table",
                            "category_name": "table",
                            "text": table_text
                        }
                        page_chunks.append(table_block)

            continuous_chunks.extend(page_chunks)
            page_wise_chunks.append(page_chunks)

    except Exception as e:
        logger.exception(f"fetch_data_from_doc failed: {e}")

    return continuous_chunks, page_wise_chunks

def get_doc_data(filepath: str, analyzer) -> Dict:
    """
    Load and parse full document.
    """
    doc_iter = load_doc(filepath, analyzer)

    continuous_chunks, page_chunks = fetch_data_from_doc(doc_iter)

    if not continuous_chunks:
        return {}

    return {
        "doc_id": continuous_chunks[0].get("document_id"),
        "doc_path": filepath,
        "continuous_chunks": continuous_chunks,
        "page_chunks": page_chunks
    }


# ---------------------------
# Chunking Logic
# ---------------------------
class Chunk:
    """
    Represents a contiguous layout-aware chunk.
    """

    def __init__(self, max_length: int = 200):
        self.text = ""
        self.page_numbers = []
        self.categories = []
        self.titles = []
        self.max_length = max_length
        self.doc_id = None

    def accumulate(self, block: Dict) -> bool:
        text = block["text"]
        category = block["category_name"]

        self.page_numbers.append(block["page_number"])
        self.categories.append(category)

        if category == "title":
            self.titles.append(text)

        if category in ("table", "text") or len(text) >= 50:
            self.text += "\n" + text
        else:
            self.text += "\n\n" + text

        return True

    def chunking_rules(self, block: Dict) -> bool:
        word_count = len(self.text.split())

        if not self.categories:
            self.doc_id = block["document_id"]
            return self.accumulate(block)

        if (
            word_count < self.max_length
            and "title" in self.categories[-2:]
        ):
            return self.accumulate(block)

        if word_count > self.max_length:
            return False

        if (
            word_count > (self.max_length // 4)
            and block["category_name"] == "title"
        ):
            return False

        return self.accumulate(block)


def layout_chunker(all_blocks: List[Dict]) -> List[Chunk]:
    """
    Merge parsed blocks into layout-aware chunks.
    """
    all_chunks = []
    chunk = Chunk()

    for block in all_blocks:
        accumulated = chunk.chunking_rules(block)
        if not accumulated:
            all_chunks.append(chunk)
            chunk = Chunk()
            chunk.chunking_rules(block)

    if chunk.text.strip():
        all_chunks.append(chunk)

    return all_chunks


# ---------------------------
# Parsed Document Container
# ---------------------------
class ParsedDoc:
    def __init__(self):
        self.doc_id = None
        self.doc_path = None
        self.chunks = []

    def parse(self, loaded_doc):
        self.doc_id = loaded_doc.get("doc_id")
        self.doc_path = loaded_doc.get("doc_path")
        self.chunks = layout_chunker(
            loaded_doc.get("continuous_chunks", [])
        )


# ---------------------------
# Main Processing Function
# ---------------------------
def process_document(pdf_path: str, output_dir: str):
    analyzer = init_analyzer()

    loaded_doc = get_doc_data(pdf_path, analyzer)
    if not loaded_doc:
        raise RuntimeError("Failed to parse document")

    parsed_doc = ParsedDoc()
    parsed_doc.parse(loaded_doc)

    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.basename(pdf_path).replace(".pdf", ".pkl")
    output_path = os.path.join(output_dir, file_name)

    with open(output_path, "wb") as f:
        pickle.dump(parsed_doc, f)

    logger.info(f"Saved parsed document to {output_path}")
    return parsed_doc


# ---------------------------
# CLI Entry Point
# ---------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Layout-aware PDF text extraction using DeepDocDetection"
    )
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--output", default="./parsed_docs", help="Output directory")

    args = parser.parse_args()

    process_document(args.pdf, args.output)
