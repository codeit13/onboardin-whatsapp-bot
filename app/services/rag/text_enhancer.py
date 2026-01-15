"""
Text Enhancer - Uses LLM to improve extracted text before chunking
Designed to prevent hallucination by using strict prompts and low temperature
"""
import logging
from typing import Optional
from app.core.config import get_settings
from app.services.rag.llm_service import get_llm_service

logger = logging.getLogger(__name__)
settings = get_settings()


class TextEnhancer:
    """Enhance extracted text using LLM before chunking"""
    
    def __init__(self):
        self.enabled = settings.TEXT_ENHANCEMENT_ENABLED
        self.temperature = settings.TEXT_ENHANCEMENT_TEMPERATURE
        
        if self.enabled:
            try:
                # Use Groq for text enhancement (faster, cheaper)
                self.llm_service = get_llm_service(
                    provider="groq",
                    api_key=settings.GROQ_API_KEY,
                    model_name=settings.GROQ_MODEL_NAME
                )
                logger.info("✅ Text enhancer initialized with Groq")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize text enhancer: {str(e)}")
                logger.warning("   Text enhancement will be disabled. Documents will be processed without enhancement.")
                self.enabled = False
                self.llm_service = None
        else:
            self.llm_service = None
            logger.info("ℹ️  Text enhancement is disabled")
    
    def enhance_text(self, text: str, document_title: Optional[str] = None,
                     document_type: Optional[str] = None) -> str:
        """
        Enhance extracted text using LLM
        
        The LLM will:
        - Clean and normalize text
        - Fix OCR errors
        - Improve formatting
        - Remove irrelevant content
        - Preserve all factual information
        
        Args:
            text: Raw extracted text
            document_title: Document title for context
            document_type: Document type (PDF, DOCX, etc.)
            
        Returns:
            Enhanced text (or original if enhancement fails/disabled)
        """
        if not self.enabled or not self.llm_service:
            return text
        
        try:
            logger.info(f"🔄 Enhancing text using LLM (length: {len(text)} chars)...")
            
            # Build system prompt - strict instructions to prevent hallucination
            system_prompt = """You are a text cleaning and enhancement assistant. Your task is to improve extracted document text WITHOUT adding, changing, or inventing any information.

STRICT RULES:
1. DO NOT add any new information that is not in the original text
2. DO NOT change facts, numbers, dates, or names
3. DO NOT invent or assume missing information
4. DO NOT summarize or condense - preserve all content
5. ONLY fix: formatting, OCR errors, spacing, line breaks
6. Preserve the exact meaning and all details

What you CAN do:
- Fix obvious OCR errors, spelling mistakes and formatting issues
- Normalize whitespace and line breaks
- Fix broken words at line boundaries (e.g., "attendance" split as "attend-\nance" should become "attendance")
- Join words that were incorrectly split across lines
- Remove excessive blank lines
- Improve paragraph structure
- Fix punctuation errors
- Ensure sentences are complete and properly formatted

What you CANNOT do:
- Add missing information
- Change numbers or dates
- Interpret or explain content
- Add context that wasn't in original
- Remove factual content

Return ONLY the cleaned text, nothing else."""

            # Build user prompt
            context_info = []
            if document_title:
                context_info.append(f"Document Title: {document_title}")
            if document_type:
                context_info.append(f"Document Type: {document_type}")
            
            context_str = "\n".join(context_info) if context_info else "Unknown document"
            
            user_prompt = f"""Clean and enhance the following extracted document text. This text was extracted from a document and may contain formatting issues, broken words, and fragments.

{context_str}

Extracted Text:
{text}

CRITICAL INSTRUCTIONS - Fix these common issues:
1. **Broken words across lines**: If you see words split like "attend-\nance" or "attend\nance", join them into "attendance"
2. **Orphaned fragments**: If a line starts with fragments like "le)", ")", single letters, or very short words, these are likely parts of previous words that got split. Join them with the previous line.
3. **Incomplete sentences**: Ensure sentences are complete. If a line starts with a lowercase letter and the previous line doesn't end with punctuation, they might be part of the same sentence.
4. **Line breaks in words**: Remove line breaks that appear in the middle of words
5. **Normalize spacing**: Fix excessive spaces and normalize paragraph breaks

EXAMPLES of what to fix:
- "attend-\nance" → "attendance"
- "le)\nEmployees" → "Employees" (if "le)" is clearly a fragment)
- "policy.\n\n1. Objective" → "policy.\n\n1. Objective" (keep proper paragraph breaks)
- "word1\nword2" → "word1 word2" (if they're part of same sentence)

Return ONLY the cleaned, properly formatted text. Do not add explanations or commentary."""

            # Process in chunks if text is too long (to avoid token limits)
            max_chunk_size = 8000  # Characters per chunk (safe for most models)
            
            if len(text) <= max_chunk_size:
                # Process entire text at once
                enhanced_text = self.llm_service.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=self.temperature,
                    max_tokens=min(len(text) * 2, 16000),  # Allow for expansion but limit
                )
            else:
                # Process in chunks and combine
                logger.info(f"   Text is large ({len(text)} chars), processing in chunks...")
                enhanced_chunks = []
                chunk_size = max_chunk_size
                
                for i in range(0, len(text), chunk_size):
                    chunk_text = text[i:i + chunk_size]
                    chunk_prompt = f"""Clean and enhance this portion of a document.

{context_str}

Extracted Text Portion:
{chunk_text}

Return only the cleaned text for this portion."""

                    enhanced_chunk = self.llm_service.generate(
                        prompt=chunk_prompt,
                        system_prompt=system_prompt,
                        temperature=self.temperature,
                        max_tokens=min(len(chunk_text) * 2, 8000),
                    )
                    enhanced_chunks.append(enhanced_chunk)
                
                enhanced_text = "\n\n".join(enhanced_chunks)
            
            # Validate that enhancement didn't drastically change length (safety check)
            length_ratio = len(enhanced_text) / len(text) if len(text) > 0 else 1.0
            if length_ratio < 0.5 or length_ratio > 2.0:
                logger.warning(f"⚠️  Enhanced text length changed significantly ({length_ratio:.2f}x). Using original text.")
                return text
            
            logger.info(f"✅ Text enhanced (original: {len(text)} chars, enhanced: {len(enhanced_text)} chars)")
            return enhanced_text
            
        except Exception as e:
            logger.error(f"❌ Error enhancing text: {str(e)}")
            logger.warning("   Using original text without enhancement")
            return text  # Return original text on error
    
    def enhance_ocr_text(self, text: str, document_title: Optional[str] = None,
                        source_type: Optional[str] = None) -> str:
        """
        Enhance OCR-extracted text using LLM with focus on structuring and correcting OCR errors
        
        Specifically designed for OCR text which often has:
        - Broken words
        - Incorrect spacing
        - Missing punctuation
        - Poor structure
        - OCR character recognition errors
        
        Args:
            text: Raw OCR-extracted text
            document_title: Document title for context
            source_type: Source type (e.g., "image_ocr", "pdf_ocr")
            
        Returns:
            Enhanced and structured text (or original if enhancement fails/disabled)
        """
        if not self.enabled or not self.llm_service:
            return text
        
        try:
            logger.info(f"🔄 Enhancing OCR text using LLM (length: {len(text)} chars)...")
            
            # Build system prompt - specific for OCR text enhancement with aggressive error correction
            system_prompt = """You are a specialized OCR text correction expert. Your task is to aggressively fix OCR character recognition errors by making educated guesses based on context, while preserving all factual information.

AGGRESSIVE OCR ERROR CORRECTION RULES:
1. YOU MUST make educated guesses about what words SHOULD be based on context
2. Fix obvious OCR character misrecognitions (e.g., "rn"→"m", "0"→"O", "l"→"I", "ranspont"→"Transport")
3. Correct words that are clearly wrong but you can infer the correct word from context
4. Fix broken/partial words by completing them based on context
5. DO NOT add completely new information that has no basis in the OCR text
6. DO NOT change numbers, dates, or identifiers unless they're clearly OCR errors (e.g., "473595"→"673593" if context suggests)
7. Preserve the structure and all factual content

COMMON OCR ERRORS TO FIX:
- Character misrecognitions: rn→m, cl→d, li→h, vv→w, ii→n, etc.
- Word errors: "ranspont"→"Transport", "gor"→"Government", "Deparment"→"Department"
- Broken words: "AbhBh"→"AMBALAVAYAL" (if context suggests), partial words at line breaks
- Spacing errors: "GovernmentofKerala"→"Government of Kerala"
- Number errors: Fix pincodes, IDs if clearly wrong based on context (e.g., if same address has different pincode, use the correct one)
- Formatting: Remove OCR artifacts (random characters, symbols, line breaks in wrong places)

EDUCATED GUESSING ALLOWED:
- If you see "ranspont" in context of "Department", guess it's "Transport"
- If you see "gor Deparment", guess it's "Government Department"
- If you see a broken word like "AbhBh" near "AVAYAL", guess it's "AMBALAVAYAL"
- If you see similar words with slight variations, use the most common/correct one
- Use document type context (driving license, ID card, etc.) to infer correct words

WHAT YOU CANNOT DO:
- Add completely new fields or information not present in OCR
- Change names unless clearly an OCR error (e.g., "JESSAN" stays "JESSAN" unless context shows it's wrong)
- Invent addresses or details
- Add explanations or interpretations

For structured documents (IDs, licenses, certificates, forms):
- Organize into clear field-value pairs
- Fix field names (e.g., "S/D/Wof"→"Son/Daughter/Wife of")
- Group related information
- Remove duplicate text (e.g., repeated "Government of Kerala Transport Department")
- Fix formatting and structure

Return ONLY the corrected and structured text, nothing else."""

            # Build user prompt
            context_info = []
            if document_title:
                context_info.append(f"Document/Image: {document_title}")
            if source_type:
                context_info.append(f"Source Type: {source_type}")
            
            context_str = "\n".join(context_info) if context_info else "OCR-extracted text"
            
            user_prompt = f"""AGGRESSIVELY correct and enhance the following OCR-extracted text. This text has many OCR character recognition errors that need to be fixed by making educated guesses based on context.

{context_str}

OCR Extracted Text (with many errors):
{text}

CRITICAL INSTRUCTIONS - BE AGGRESSIVE:
1. **Fix obvious OCR errors**: Look for words that are clearly wrong and guess the correct word
   - "ranspont" → "Transport" (in context of Department)
   - "gor Deparment" → "Government Department"
   - "AbhBh" → "AMBALAVAYAL" (if near similar text)
   - "GovernmentofKerala" → "Government of Kerala"

2. **Fix character misrecognitions**: 
   - rn→m, cl→d, li→h, vv→w, ii→n, 0→O (when in text context), l→I (when in text context)
   - Fix based on what makes sense in context

3. **Fix broken/partial words**: Complete words that are cut off or broken
   - "gor" → "Government" (if context suggests)
   - Partial words at line breaks → complete them

4. **Fix spacing and formatting**:
   - Remove excessive spaces
   - Add missing spaces in compound words
   - Remove duplicate text (e.g., repeated department names)
   - Fix line breaks in wrong places

5. **Fix numbers if clearly wrong**:
   - If same field appears with different values, use the correct one
   - Fix pincodes if context suggests (e.g., if address is same but pincode differs)

6. **Structure the information**:
   - Organize into clear field-value pairs
   - Fix field names (e.g., "S/D/Wof" → "Son/Daughter/Wife of")
   - Remove OCR artifacts (random symbols, characters)

7. **Preserve factual information**:
   - Keep all names, dates, numbers (unless clearly OCR errors)
   - Keep all addresses and details
   - Don't add new information

MAKE EDUCATED GUESSES based on:
- Document type (driving license, ID card, etc.)
- Context of surrounding words
- Common words and phrases
- Pattern recognition (e.g., if "Transport" appears correctly elsewhere, fix "ranspont" to "Transport")

Return ONLY the corrected, structured text without any explanations or commentary."""

            # Process in chunks if text is too long
            max_chunk_size = 8000  # Characters per chunk
            
            if len(text) <= max_chunk_size:
                # Process entire text at once
                # Use slightly higher temperature for OCR text to allow more creative error correction
                ocr_temperature = min(self.temperature + 0.1, 0.4)  # Slightly higher but still controlled
                
                enhanced_text = self.llm_service.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=ocr_temperature,
                    max_tokens=min(len(text) * 2, 16000),
                )
            else:
                # Process in chunks and combine
                logger.info(f"   OCR text is large ({len(text)} chars), processing in chunks...")
                enhanced_chunks = []
                chunk_size = max_chunk_size
                
                for i in range(0, len(text), chunk_size):
                    chunk_text = text[i:i + chunk_size]
                    chunk_prompt = f"""AGGRESSIVELY correct this portion of OCR-extracted text by fixing OCR errors and making educated guesses.

{context_str}

OCR Text Portion (with errors):
{chunk_text}

Fix OCR errors aggressively:
- Character misrecognitions (rn→m, etc.)
- Broken words (complete them based on context)
- Spacing issues
- Obvious word errors (e.g., "ranspont"→"Transport")
- Remove duplicates and artifacts

Return only the corrected text for this portion."""

                    # Use slightly higher temperature for OCR text
                    ocr_temperature = min(self.temperature + 0.1, 0.4)
                    
                    enhanced_chunk = self.llm_service.generate(
                        prompt=chunk_prompt,
                        system_prompt=system_prompt,
                        temperature=ocr_temperature,
                        max_tokens=min(len(chunk_text) * 2, 8000),
                    )
                    enhanced_chunks.append(enhanced_chunk)
                
                enhanced_text = "\n\n".join(enhanced_chunks)
            
            # Validate that enhancement didn't drastically change length
            length_ratio = len(enhanced_text) / len(text) if len(text) > 0 else 1.0
            if length_ratio < 0.5 or length_ratio > 2.0:
                logger.warning(f"⚠️  Enhanced OCR text length changed significantly ({length_ratio:.2f}x). Using original text.")
                return text
            
            logger.info(f"✅ OCR text enhanced (original: {len(text)} chars, enhanced: {len(enhanced_text)} chars)")
            return enhanced_text
            
        except Exception as e:
            logger.error(f"❌ Error enhancing OCR text: {str(e)}")
            logger.warning("   Using original OCR text without enhancement")
            return text  # Return original text on error
