"""
DeepDocDetection Parser Service - Layout-aware document parsing for PDFs and images
"""
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Lazy import to avoid loading deepdoctection if not needed
try:
    import deepdoctection as dd
    DEEPDOCTECTION_AVAILABLE = True
except ImportError:
    DEEPDOCTECTION_AVAILABLE = False
    logger.warning("deepdoctection not available. Install with: pip install deepdoctection")


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


class DeepDocDetectionParser:
    """
    Service for parsing PDFs and images using DeepDocDetection with layout awareness.
    """
    
    def __init__(self, doc_lang: str = "en", max_chunk_length: int = 200):
        """
        Initialize the DeepDocDetection parser.
        
        Args:
            doc_lang: Document language code (default: "en")
            max_chunk_length: Maximum word count per chunk (default: 200)
        """
        if not DEEPDOCTECTION_AVAILABLE:
            raise ImportError(
                "deepdoctection is not available. "
                "Install with: pip install deepdoctection"
            )
        
        self.doc_lang = doc_lang
        self.max_chunk_length = max_chunk_length
        self._analyzer = None
        logger.info("Initialized DeepDocDetectionParser")
    
    @property
    def analyzer(self):
        """Lazy initialization of the analyzer"""
        if self._analyzer is None:
            logger.info("Initializing DeepDocDetection analyzer (this may take a moment)...")
            self._analyzer = dd.get_dd_analyzer()
            logger.info("DeepDocDetection analyzer initialized successfully")
        return self._analyzer
    
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a PDF or image file and return structured chunks.
        
        Args:
            file_path: Path to the PDF or image file
            
        Returns:
            Dictionary containing:
                - text: Combined text from all chunks
                - chunks: List of chunk dictionaries with text and metadata
                - file_path: Original file path
                - doc_id: Document ID from parser
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = Path(file_path).suffix.lower()
        
        # DeepDocDetection supports both PDFs and images
        if file_ext not in [".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
            raise ValueError(
                f"Unsupported file type: {file_ext}. "
                "DeepDocDetection supports PDFs and common image formats."
            )
        
        logger.info(f"Parsing file with DeepDocDetection: {file_path}")
        
        try:
            # Load and analyze document
            doc_iter = self._load_doc(file_path)
            
            # Extract data from document
            continuous_chunks, page_chunks = self._fetch_data_from_doc(doc_iter)
            
            if not continuous_chunks:
                logger.warning(f"No content extracted from {file_path}")
                return {
                    "text": "",
                    "chunks": [],
                    "file_path": file_path,
                    "doc_id": None
                }
            
            # Create layout-aware chunks
            layout_chunks = self._layout_chunker(continuous_chunks)
            
            # Convert to document processor format
            chunks = []
            combined_text = []
            
            for idx, chunk in enumerate(layout_chunks):
                chunk_text = chunk.text.strip()
                if chunk_text:
                    combined_text.append(chunk_text)
                    chunks.append({
                        "text": chunk_text,
                        "chunk_index": idx,
                        "page_numbers": sorted(set(chunk.page_numbers)),
                        "titles": chunk.titles,
                        "categories": chunk.categories,
                        "doc_id": chunk.doc_id,
                        "start": 0,  # Not tracking exact positions
                        "end": len(chunk_text),
                    })
            
            combined_text_str = "\n\n".join(combined_text)
            
            logger.info(
                f"Successfully parsed {file_path}: "
                f"{len(chunks)} chunks, {len(combined_text_str)} characters"
            )
            
            return {
                "text": combined_text_str,
                "chunks": chunks,
                "file_path": file_path,
                "doc_id": continuous_chunks[0].get("document_id") if continuous_chunks else None
            }
            
        except Exception as e:
            logger.error(f"Error parsing file {file_path} with DeepDocDetection: {str(e)}", exc_info=True)
            raise
    
    def _load_doc(self, path: str):
        """Load and analyze document"""
        file_ext = Path(path).suffix.lower()
        
        # For images, deepdoctection requires bytes to be passed (without path for single images)
        if file_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
            with open(path, "rb") as f:
                image_bytes = f.read()
            # For single images, pass only b_bytes without path
            df = self.analyzer.analyze(b_bytes=image_bytes)
        else:
            # For PDFs, just pass the path
            df = self.analyzer.analyze(path=path)
        
        df.reset_state()
        return iter(df)
    
    def _table_html_to_semantic_text(self, table_html: str) -> str:
        """Convert HTML table to embedding-friendly semantic text"""
        soup = BeautifulSoup(table_html, "html.parser")
        rows = soup.find_all("tr")
        
        lines = []
        for row in rows:
            cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
            if cells:
                lines.append(" | ".join(cells))
        
        if not lines:
            return ""
        
        return "\n Table:\n"+"\n".join(lines) + "\n"
    
    def _get_block_data(self, block) -> Dict:
        """Extract relevant metadata from a block"""
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
    
    def _get_page_data(self, page) -> List[Dict]:
        """Extract all parsed blocks from a page"""
        all_blocks = []
        try:
            for block in page.chunks:
                all_blocks.append(self._get_block_data(block))
        except Exception as e:
            logger.exception(f"Error parsing page {page.page_number}: {e}")
        return all_blocks
    
    def _fetch_data_from_doc(self, doc) -> Tuple[List[Dict], List[List[Dict]]]:
        """
        Fetch parsed text blocks and inject tables as semantic text blocks.
        Preserves correct reading order by sorting blocks including tables based on position.
        
        Returns:
            Tuple of (continuous_chunks, page_wise_chunks)
        """
        continuous_chunks = []
        page_wise_chunks = []
        
        try:
            for page in doc:
                page_chunks = self._get_page_data(page)
                
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
                        table_text = self._table_html_to_semantic_text(table.html)
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
    
    def _layout_chunker(self, all_blocks: List[Dict]) -> List[Chunk]:
        """Merge parsed blocks into layout-aware chunks"""
        all_chunks = []
        chunk = Chunk(max_length=self.max_chunk_length)
        
        for block in all_blocks:
            accumulated = chunk.chunking_rules(block)
            if not accumulated:
                all_chunks.append(chunk)
                chunk = Chunk(max_length=self.max_chunk_length)
                chunk.chunking_rules(block)
        
        if chunk.text.strip():
            all_chunks.append(chunk)
        
        return all_chunks
