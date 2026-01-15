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
    reading_order = block[4]
    # Convert reading_order to int if possible, otherwise use a large number for sorting
    try:
        reading_order_int = int(reading_order) if reading_order not in (None, "table", "") else 999999
    except (ValueError, TypeError):
        reading_order_int = 999999
    
    # Try to extract bbox (bounding box) Y coordinate for vertical positioning
    bbox_y = None
    try:
        # Block format: (doc_id, image_id, page_num, annotation_id, reading_order, ..., layout_item)
        # Try multiple ways to access bbox
        if len(block) > 5:
            layout_item = block[-2]  # Second to last is the layout item
            
            # Try direct bbox attribute
            if hasattr(layout_item, 'bbox'):
                bbox = layout_item.bbox
                if bbox:
                    if hasattr(bbox, 'uly'):
                        bbox_y = bbox.uly
                    elif hasattr(bbox, 'upper_left'):
                        bbox_y = bbox.upper_left.y
                    elif isinstance(bbox, (list, tuple)) and len(bbox) >= 2:
                        bbox_y = bbox[1]  # Usually (x, y, width, height) or similar
            
            # Try nested bbox
            if bbox_y is None and hasattr(layout_item, 'block'):
                block_obj = layout_item.block
                if hasattr(block_obj, 'bbox'):
                    bbox = block_obj.bbox
                    if hasattr(bbox, 'uly'):
                        bbox_y = bbox.uly
                    elif isinstance(bbox, (list, tuple)) and len(bbox) >= 2:
                        bbox_y = bbox[1]
            
            # Try location attribute
            if bbox_y is None and hasattr(layout_item, 'location'):
                loc = layout_item.location
                if hasattr(loc, 'uly'):
                    bbox_y = loc.uly
                elif hasattr(loc, 'y'):
                    bbox_y = loc.y
    except (AttributeError, IndexError, TypeError) as e:
        logger.debug(f"Could not extract bbox_y: {e}")
    
    block_data = {
        "document_id": str(block[0]),
        "image_id": str(block[1]),
        "page_number": str(block[2]),
        "annotation_id": str(block[3]),
        "reading_order": str(reading_order),
        "reading_order_int": reading_order_int,  # For sorting
        "bbox_y": bbox_y,  # Y coordinate for vertical positioning
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
    Preserves correct reading order by sorting blocks including tables.
    """
    continuous_chunks = []
    page_wise_chunks = []

    try:
        for page in doc:
            page_chunks = get_page_data(page)
            
            # Get the last reading_order value from existing blocks to position tables
            max_reading_order = 0
            if page_chunks:
                max_reading_order = max(
                    (chunk.get("reading_order_int", 0) for chunk in page_chunks),
                    default=0
                )

            # Create table blocks and extract their bounding boxes
            table_blocks = []
            if page.tables:
                for idx, table in enumerate(page.tables):
                    table_text = table_html_to_semantic_text(table.html)
                    if table_text.strip():
                        # Try to get table bounding box for positioning
                        table_bbox_y = None
                        try:
                            # Try multiple ways to get table bbox
                            if hasattr(table, 'bbox') and table.bbox:
                                bbox = table.bbox
                                if hasattr(bbox, 'uly'):
                                    table_bbox_y = bbox.uly
                                elif hasattr(bbox, 'upper_left'):
                                    table_bbox_y = bbox.upper_left.y
                                elif isinstance(bbox, (list, tuple)) and len(bbox) >= 2:
                                    table_bbox_y = bbox[1]
                            
                            if table_bbox_y is None and hasattr(table, 'location'):
                                loc = table.location
                                if hasattr(loc, 'uly'):
                                    table_bbox_y = loc.uly
                                elif hasattr(loc, 'y'):
                                    table_bbox_y = loc.y
                            
                            # Try accessing through table attributes
                            if table_bbox_y is None and hasattr(table, 'block'):
                                block = table.block
                                if hasattr(block, 'bbox'):
                                    bbox = block.bbox
                                    if hasattr(bbox, 'uly'):
                                        table_bbox_y = bbox.uly
                        except (AttributeError, TypeError) as e:
                            logger.debug(f"Could not extract table bbox_y: {e}")
                        
                        table_block = {
                            "document_id": page_chunks[0]["document_id"] if page_chunks else "",
                            "image_id": "",
                            "page_number": str(page.page_number),
                            "annotation_id": f"table_{idx}",
                            "reading_order": "",  # Will be assigned after sorting
                            "reading_order_int": 0,  # Will be assigned after sorting
                            "bbox_y": table_bbox_y,  # Y coordinate for sorting
                            "category_name": "table",
                            "text": table_text
                        }
                        table_blocks.append(table_block)
            
            # Merge all blocks (text blocks + tables)
            all_page_blocks = page_chunks + table_blocks
            
            # Check if we have bbox_y for most blocks (to decide sorting strategy)
            blocks_with_bbox = sum(1 for b in all_page_blocks if b.get("bbox_y") is not None)
            total_blocks = len(all_page_blocks)
            use_bbox_sorting = blocks_with_bbox >= max(2, total_blocks // 2)  # Use bbox if at least half have it
            
            if use_bbox_sorting:
                # Sort ALL blocks by bbox_y (vertical position) - smaller Y = higher on page = earlier
                # Items with no bbox_y go to the end, but try to preserve their relative order
                all_page_blocks.sort(key=lambda x: (
                    x.get("bbox_y") if x.get("bbox_y") is not None else 999999,
                    x.get("reading_order_int", 999999)  # Secondary sort by original reading_order
                ))
                
                # Now assign sequential reading_order based on sorted position
                for idx, block in enumerate(all_page_blocks):
                    block["reading_order_int"] = idx
                    block["reading_order"] = str(idx)
            else:
                # Fallback: preserve original reading_order and insert tables intelligently
                # Sort by original reading_order_int first
                all_page_blocks.sort(key=lambda x: x.get("reading_order_int", 999999))
                
                # If we have some bbox_y data, try to reposition tables
                for table_block in table_blocks:
                    table_bbox_y = table_block.get("bbox_y")
                    if table_bbox_y is not None:
                        # Find insertion point based on Y-coordinate
                        insertion_idx = len(all_page_blocks)  # Default: end
                        for i, block in enumerate(all_page_blocks):
                            block_bbox_y = block.get("bbox_y")
                            block_ro_int = block.get("reading_order_int", 999999)
                            if block_bbox_y is not None and block_bbox_y < table_bbox_y:
                                # This block is above the table, table should come after
                                insertion_idx = max(insertion_idx, i + 1)
                        
                        # Remove table from end and insert at correct position
                        if table_block in all_page_blocks:
                            all_page_blocks.remove(table_block)
                            all_page_blocks.insert(min(insertion_idx, len(all_page_blocks)), table_block)
            
            # Clean up temporary bbox_y field before returning
            for block in all_page_blocks:
                block.pop("bbox_y", None)

            continuous_chunks.extend(all_page_blocks)
            page_wise_chunks.append(all_page_blocks)

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
