"""
Document Processor - Handles various document formats and OCR
"""
import logging
import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from app.core.config import get_settings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentProcessor:
    """Process various document formats and extract text"""
    
    def __init__(self, text_enhancer=None):
        self.ocr_enabled = settings.OCR_ENABLED
        self.ocr_language = settings.OCR_LANGUAGE
        self.text_enhancer = text_enhancer  # Optional TextEnhancer for LLM-based text improvement
        self.use_deepdoctection = settings.USE_DEEPDOCTECTION
        self._deepdoctection_parser = None
        
        if self.use_deepdoctection:
            try:
                from app.services.rag.deepdoctection_parser import DeepDocDetectionParser
                self._deepdoctection_parser = DeepDocDetectionParser(
                    doc_lang="en",
                    max_chunk_length=200  # Can be made configurable if needed
                )
                logger.info("DeepDocDetection parser initialized")
            except ImportError as e:
                logger.warning(f"DeepDocDetection requested but not available: {e}. Falling back to default processors.")
                self.use_deepdoctection = False
        
        logger.info(
            f"Initialized DocumentProcessor "
            f"(OCR: {self.ocr_enabled}, DeepDocDetection: {self.use_deepdoctection})"
        )
    
    def process_file(self, file_path: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a document file and extract text
        
        Args:
            file_path: Path to the document file
            mime_type: MIME type of the file (optional)
            
        Returns:
            Dictionary with extracted text, metadata, and optionally pre-chunked data
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_ext = Path(file_path).suffix.lower()
            mime_type = mime_type or self._detect_mime_type(file_path)
            
            logger.info(f"Processing file: {file_path} (type: {mime_type})")
            
            # If using DeepDocDetection for PDFs or images, get chunks directly
            if self.use_deepdoctection and self._deepdoctection_parser:
                if file_ext == ".pdf" or file_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
                    try:
                        result = self._deepdoctection_parser.parse_file(file_path)
                        # Return with pre-chunked data
                        return {
                            "text": result["text"],
                            "chunks": result["chunks"],  # Pre-chunked layout-aware chunks
                            "file_path": file_path,
                            "mime_type": mime_type,
                            "file_ext": file_ext,
                            "doc_id": result.get("doc_id"),
                            "use_deepdoctection": True,
                        }
                    except Exception as e:
                        logger.warning(
                            f"DeepDocDetection processing failed: {str(e)}. "
                            "Falling back to default processor."
                        )
                        # Fall through to default processors
            
            # Route to appropriate processor (default flow)
            if file_ext == ".pdf":
                text = self._process_pdf(file_path)
            elif file_ext in [".docx", ".doc"]:
                text = self._process_docx(file_path)
            elif file_ext == ".txt":
                text = self._process_txt(file_path)
            elif file_ext in [".md", ".markdown"]:
                text = self._process_markdown(file_path)
            elif file_ext == ".html":
                text = self._process_html(file_path)
            elif file_ext == ".csv":
                text = self._process_csv(file_path)
            elif file_ext in [".xlsx", ".xls"]:
                text = self._process_excel(file_path)
            elif file_ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
                text = self._process_image(file_path)
            else:
                # Try to read as text
                text = self._process_txt(file_path)
            
            return {
                "text": text,
                "file_path": file_path,
                "mime_type": mime_type,
                "file_ext": file_ext,
                "use_deepdoctection": False,
            }
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise
    
    def chunk_text(self, text: str, chunk_size: Optional[int] = None,
                  chunk_overlap: Optional[int] = None,
                  title: Optional[str] = None,
                  pre_chunked: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Split text into chunks using LangChain's RecursiveCharacterTextSplitter,
        or use pre-chunked data if provided (e.g., from DeepDocDetection).
        
        Args:
            text: Text to chunk (ignored if pre_chunked is provided)
            chunk_size: Size of each chunk (characters)
            chunk_overlap: Overlap between chunks (characters)
            title: Document title to add as context to chunks
            pre_chunked: Pre-chunked data from DeepDocDetection (optional)
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        # If pre-chunked data is available (from DeepDocDetection), use it directly
        if pre_chunked:
            logger.info(f"📦 Using {len(pre_chunked)} pre-chunked layout-aware chunks from DeepDocDetection")
            # Add title context if provided
            if title:
                for chunk in pre_chunked:
                    if "text" in chunk:
                        chunk["text"] = f"Document: {title}\n\n{chunk['text']}"
            return pre_chunked
        
        # Default chunking using LangChain
        chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
        
        # Clean text first
        text = self._clean_text(text)
        
        if not text.strip():
            return []
        
        # Use LangChain's RecursiveCharacterTextSplitter
        # This splits text recursively by characters, trying to keep paragraphs, sentences, and words together
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],  # Try to split by paragraphs, then lines, then sentences, then words
            is_separator_regex=False,
        )
        
        # Split the text
        langchain_chunks = text_splitter.split_text(text)
        
        # Convert to our format
        chunks = []
        for i, chunk_text in enumerate(langchain_chunks):
            chunks.append(self._create_chunk(chunk_text.strip(), i, title))
        
        logger.info(f"📦 Created {len(chunks)} chunks using LangChain (chunk_size: {chunk_size}, overlap: {chunk_overlap})")
        logger.info(f"   Avg chunk size: {sum(len(c['text']) for c in chunks) // len(chunks) if chunks else 0} chars")
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        import re
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double
        # Fix broken words at line boundaries (common in PDFs)
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)  # Fix hyphenated words split across lines
        text = re.sub(r'(\w+)\s*\n\s*(\w+)', r'\1 \2', text)  # Fix words split across lines
        return text.strip()
    
    def _create_chunk(self, text: str, chunk_index: int, title: Optional[str] = None) -> Dict[str, Any]:
        """Create a chunk dictionary"""
        text = text.strip()
        if title:
            text = f"Document: {title}\n\n{text}"
        return {
            "text": text,
            "chunk_index": chunk_index,
            "start": 0,  # Not tracking exact positions anymore
            "end": len(text),
        }
    
    def _process_pdf(self, file_path: str) -> str:
        """Process PDF file using DeepDocDetection (if enabled) or LangChain PyPDFLoader"""
        # Use DeepDocDetection if enabled
        if self.use_deepdoctection and self._deepdoctection_parser:
            try:
                logger.info(f"Processing PDF with DeepDocDetection: {file_path}")
                result = self._deepdoctection_parser.parse_file(file_path)
                return result["text"]
            except Exception as e:
                logger.warning(
                    f"DeepDocDetection PDF processing failed: {str(e)}. "
                    "Falling back to default PDF processor."
                )
                # Fall through to default processor
        
        # Default PDF processing using LangChain PyPDFLoader
        try:
            from langchain_community.document_loaders import PyPDFLoader
        except ImportError as e:
            logger.error(f"Failed to import PyPDFLoader: {str(e)}")
            raise ImportError("langchain-community is required. Install with: pip install langchain-community")
        
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            
            # Combine all pages into a single text
            text = "\n\n".join([doc.page_content for doc in documents])
            
            # If text extraction failed or is minimal, try OCR
            if len(text.strip()) < 100 and self.ocr_enabled:
                logger.info(f"PDF text extraction yielded little text, trying OCR...")
                text = self._ocr_image(file_path)
            
            return text
        except ModuleNotFoundError as e:
            error_msg = str(e)
            if 'pypdf' in error_msg.lower():
                logger.error(f"pypdf package not found: {error_msg}")
                raise ImportError("pypdf package is required for PDF processing. Install with: pip install pypdf")
            raise
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
            raise
    
    def _process_docx(self, file_path: str) -> str:
        """Process DOCX file using LangChain DocxLoader"""
        try:
            from langchain_community.document_loaders import Docx2txtLoader
            
            loader = Docx2txtLoader(file_path)
            documents = loader.load()
            
            # Combine all documents into a single text
            text = "\n\n".join([doc.page_content for doc in documents])
            return text
        except ImportError:
            raise ImportError("langchain-community is required. Install with: pip install langchain-community")
        except Exception as e:
            logger.error(f"Error processing DOCX: {str(e)}")
            raise
    
    def _process_txt(self, file_path: str) -> str:
        """Process text file using LangChain TextLoader"""
        try:
            from langchain_community.document_loaders import TextLoader
            
            loader = TextLoader(file_path, encoding='utf-8')
            documents = loader.load()
            
            # Combine all documents into a single text
            text = "\n\n".join([doc.page_content for doc in documents])
            return text
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                from langchain_community.document_loaders import TextLoader
                loader = TextLoader(file_path, encoding='latin-1')
                documents = loader.load()
                text = "\n\n".join([doc.page_content for doc in documents])
                return text
            except Exception as e:
                logger.error(f"Error processing text file with different encoding: {str(e)}")
                raise
        except ImportError:
            raise ImportError("langchain-community is required. Install with: pip install langchain-community")
        except Exception as e:
            logger.error(f"Error processing text file: {str(e)}")
            raise
    
    def _process_markdown(self, file_path: str) -> str:
        """Process Markdown file using LangChain TextLoader"""
        # Markdown can be processed as text
        return self._process_txt(file_path)
    
    def _process_html(self, file_path: str) -> str:
        """Process HTML file using LangChain BSHTMLLoader"""
        try:
            from langchain_community.document_loaders import BSHTMLLoader
            
            loader = BSHTMLLoader(file_path)
            documents = loader.load()
            
            # Combine all documents into a single text
            text = "\n\n".join([doc.page_content for doc in documents])
            return text
        except ImportError:
            raise ImportError("langchain-community is required. Install with: pip install langchain-community")
        except Exception as e:
            logger.error(f"Error processing HTML: {str(e)}")
            raise
    
    def _process_csv(self, file_path: str) -> str:
        """Process CSV file using LangChain CSVLoader"""
        try:
            from langchain_community.document_loaders import CSVLoader
            
            loader = CSVLoader(file_path)
            documents = loader.load()
            
            # Combine all documents into a single text
            text = "\n\n".join([doc.page_content for doc in documents])
            return text
        except ImportError:
            raise ImportError("langchain-community is required. Install with: pip install langchain-community")
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            raise
    
    def _process_excel(self, file_path: str) -> str:
        """Process Excel file using LangChain UnstructuredExcelLoader"""
        try:
            from langchain_community.document_loaders import UnstructuredExcelLoader
            
            loader = UnstructuredExcelLoader(file_path)
            documents = loader.load()
            
            # Combine all documents into a single text
            text = "\n\n".join([doc.page_content for doc in documents])
            return text
        except ImportError:
            # Fallback to pandas if unstructured is not available
            try:
                import pandas as pd
                df = pd.read_excel(file_path)
                return df.to_string()
            except ImportError:
                raise ImportError("langchain-community or pandas+openpyxl is required. Install with: pip install langchain-community")
        except Exception as e:
            logger.error(f"Error processing Excel: {str(e)}")
            raise
    
    def _process_image(self, file_path: str) -> str:
        """Process image file with DeepDocDetection (if enabled) or OCR"""
        # Use DeepDocDetection if enabled
        if self.use_deepdoctection and self._deepdoctection_parser:
            try:
                logger.info(f"Processing image with DeepDocDetection: {file_path}")
                result = self._deepdoctection_parser.parse_file(file_path)
                return result["text"]
            except Exception as e:
                logger.warning(
                    f"DeepDocDetection image processing failed: {str(e)}. "
                    "Falling back to OCR."
                )
                # Fall through to OCR
        
        # Default image processing with OCR
        if not self.ocr_enabled:
            logger.warning("OCR is disabled. Cannot process image.")
            return ""
        
        return self._ocr_image(file_path)
    
    def _ocr_image(self, file_path: str) -> str:
        """
        Perform OCR on image with automatic orientation correction
        
        Uses Tesseract's built-in Orientation and Script Detection (OSD) to:
        - Detect image orientation automatically
        - Rotate image to correct orientation
        - Handle EXIF orientation tags (common in mobile photos)
        - Support rotated images (90°, 180°, 270°)
        """
        try:
            from PIL import Image, ImageOps, ImageChops
            import pytesseract
            import re
            
            # Open image
            image = Image.open(file_path)
            
            # Step 1: Fix orientation based on EXIF data (common in mobile photos)
            try:
                # ImageOps.exif_transpose automatically rotates based on EXIF orientation tag
                image = ImageOps.exif_transpose(image)
                logger.info("Applied EXIF orientation correction")
            except Exception as e:
                logger.debug(f"EXIF orientation correction not needed or failed: {str(e)}")
            
            # Step 2: Use Tesseract's OSD (Orientation and Script Detection) to detect rotation
            try:
                # OSD works better on color images, so try original if available
                # But we'll apply rotation to the EXIF-corrected image
                osd_image = image
                
                # Get orientation detection result
                osd_result = pytesseract.image_to_osd(osd_image)
                logger.info(f"Tesseract OSD result: {osd_result}")
                
                # Extract rotation angle from OSD output
                # Format: "Rotate: 270" or "Rotate: 90" etc.
                rotate_match = re.search(r"Rotate:\s*(\d+)", osd_result)
                orientation_match = re.search(r"Orientation in degrees:\s*(\d+)", osd_result)
                confidence_match = re.search(r"Orientation confidence:\s*([\d.]+)", osd_result)
                
                if rotate_match:
                    rotation_angle = int(rotate_match.group(1))
                    orientation_deg = int(orientation_match.group(1)) if orientation_match else None
                    confidence = float(confidence_match.group(1)) if confidence_match else None
                    
                    # Only rotate if confidence is reasonable and angle is not 0
                    if rotation_angle != 0 and (confidence is None or confidence > 0.3):
                        logger.info(f"Detected rotation: {rotation_angle}° (orientation: {orientation_deg}°, confidence: {confidence})")
                        # Tesseract OSD "Rotate" value is clockwise, but PIL rotate() is counter-clockwise
                        # So we need to negate the angle
                        pil_rotation_angle = -rotation_angle
                        image = image.rotate(pil_rotation_angle, expand=True)
                        logger.info(f"Rotated image by {pil_rotation_angle}° (OSD: {rotation_angle}° clockwise) for optimal OCR")
                    else:
                        logger.info(f"No rotation needed (angle: {rotation_angle}°, confidence: {confidence})")
                else:
                    logger.debug("Could not extract rotation angle from OSD result")
                    
            except Exception as e:
                # OSD might fail for some images (e.g., no text, too complex)
                # Fall back to regular OCR
                logger.warning(f"Tesseract OSD failed, proceeding with regular OCR: {str(e)}")
            
            # Step 3: Convert to grayscale after rotation
            if image.mode != 'L':
                image = image.convert("L")
                logger.debug("Converted image to grayscale (L mode) for OCR")
            
            # Step 3.5: Invert image (black to white, white to black)
            # This can help OCR for documents with white text on dark background
            # or inverted scanned documents
            image = ImageChops.invert(image)
            logger.debug("Inverted image colors for OCR (black→white, white→black)")
            
            # Step 4: Save processed image to disk
            try:
                # Create processed images directory
                processed_dir = Path(settings.DOCUMENTS_STORAGE_PATH) / "processed_images"
                processed_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate filename for processed image
                original_path = Path(file_path)
                processed_filename = f"{original_path.stem}_processed{original_path.suffix}"
                processed_path = processed_dir / processed_filename
                
                # Save the processed image
                image.save(processed_path, quality=95)
                logger.info(f"💾 Saved processed image to: {processed_path}")
            except Exception as e:
                logger.warning(f"Failed to save processed image: {str(e)}")
            
            # Step 5: Perform OCR on the corrected image
            text = pytesseract.image_to_string(image, lang=self.ocr_language)
            
            # Step 6: If text extraction yields very little, try alternative approach
            if len(text.strip()) < 5:
                logger.warning(f"OCR yielded little text ({len(text.strip())} chars), trying without OSD rotation...")
                # Try original image without OSD rotation (in case OSD was wrong)
                try:
                    original_image = Image.open(file_path)
                    original_image = ImageOps.exif_transpose(original_image)
                    # Convert to grayscale after EXIF correction
                    if original_image.mode != 'L':
                        original_image = original_image.convert("L")
                    # Invert image (same as main processing)
                    original_image = ImageChops.invert(original_image)
                    alt_text = pytesseract.image_to_string(original_image, lang=self.ocr_language)
                    
                    if len(alt_text.strip()) > len(text.strip()):
                        logger.info(f"Using text from original orientation ({len(alt_text.strip())} chars)")
                        text = alt_text
                except Exception as e:
                    logger.debug(f"Alternative OCR attempt failed: {str(e)}")
            
            # Step 6: Enhance OCR text using LLM (if enhancer is available)
            if self.text_enhancer and text.strip():
                logger.info("🔄 Enhancing OCR text using LLM for better structure...")
                try:
                    # Get image filename for context
                    image_name = Path(file_path).stem
                    enhanced_text = self.text_enhancer.enhance_ocr_text(
                        text=text,
                        document_title=image_name,
                        source_type="image_ocr"
                    )
                    
                    if enhanced_text != text:
                        logger.info(f"✨ OCR text enhanced: {len(text)} → {len(enhanced_text)} characters")
                        text = enhanced_text
                    else:
                        logger.info("ℹ️  OCR text enhancement skipped or unchanged")
                except Exception as e:
                    logger.warning(f"⚠️  OCR text enhancement failed: {str(e)}")
                    logger.warning("   Using original OCR text without enhancement")
            
            return text
                
        except ImportError:
            raise ImportError("pytesseract and Pillow are required. Install with: pip install pytesseract Pillow")
        except Exception as e:
            logger.error(f"Error performing OCR: {str(e)}")
            raise
    
    def _detect_mime_type(self, file_path: str) -> str:
        """Detect MIME type from file extension"""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"
