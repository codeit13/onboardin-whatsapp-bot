"""
RAG Service - Main service that orchestrates RAG functionality
"""
import logging
import os
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.services.rag.llm_service import get_llm_service
from app.services.rag.singletons import get_embedding_service_instance, get_vector_store_instance
from app.services.rag.document_processor import DocumentProcessor
from app.services.rag.website_scraper import WebsiteScraper
from app.services.rag.conversation_manager import ConversationManager
from app.services.rag.text_enhancer import TextEnhancer
from app.tables.knowledge_documents import KnowledgeDocumentRepository, DocumentType, DocumentStatus
from app.tables.user_documents import UserDocumentRepository
from app.tables.document_chunks import DocumentChunkRepository
from app.tables.users import UserRepository
from app.core.config import get_settings
from datetime import datetime

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGService:
    """Main RAG service that handles queries and document management"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Use singleton instances (initialized at app startup)
        self.llm_service = get_llm_service()
        self.embedding_service = get_embedding_service_instance()
        self.vector_store = get_vector_store_instance()
        self.text_enhancer = TextEnhancer()  # For enhancing text before chunking
        self.document_processor = DocumentProcessor(text_enhancer=self.text_enhancer)  # Pass enhancer for OCR text enhancement
        self.website_scraper = WebsiteScraper()
        self.conversation_manager = ConversationManager(db)
        
        # Initialize repositories
        self.knowledge_doc_repo = KnowledgeDocumentRepository(db)
        self.user_doc_repo = UserDocumentRepository(db)
        self.chunk_repo = DocumentChunkRepository(db)
        self.user_repo = UserRepository(db)
        
        logger.info("✅ Initialized RAGService")
    
    def query(self, user_phone_number: str, query: str,
             session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user query using RAG
        
        Args:
            user_phone_number: User's phone number
            query: User's query/question
            session_id: Optional session ID (auto-generated if not provided)
            
        Returns:
            Dictionary with response and metadata
        """
        try:
            logger.info("=" * 80)
            logger.info(f"🔍 RAG Query Request")
            logger.info(f"   User: {user_phone_number}")
            logger.info(f"   Query: {query}")
            logger.info(f"   Session ID: {session_id}")
            
            # Get or create session
            if not session_id:
                session_id = self.conversation_manager.get_session_id(user_phone_number)
            
            # Add user message to history
            self.conversation_manager.add_message(
                user_phone_number=user_phone_number,
                session_id=session_id,
                message_type="user",
                message=query,
            )
            
            # Get user's accessible documents
            user_docs = self._get_user_accessible_documents(user_phone_number)
            logger.info(f"   User accessible documents: {user_docs}")
            
            # Retrieve relevant chunks
            relevant_chunks = self._retrieve_relevant_chunks(query, user_phone_number, user_docs)
            
            # Print detailed chunk information for debugging
            logger.info(f"📄 Retrieved {len(relevant_chunks)} relevant chunks:")
            for i, chunk in enumerate(relevant_chunks, 1):
                logger.info(f"   Chunk {i}:")
                logger.info(f"      - Chunk ID: {chunk.get('chunk_id')}")
                logger.info(f"      - Document ID: {chunk.get('document_id')}")
                logger.info(f"      - Similarity: {chunk.get('similarity', 0):.4f}")
                logger.info(f"      - Text preview: {chunk.get('text', '')[:200]}...")
                logger.info(f"      - Metadata: {chunk.get('metadata', {})}")
            
            if len(relevant_chunks) == 0:
                logger.warning("⚠️  No relevant chunks found! This may indicate:")
                logger.warning("   1. No documents indexed in FAISS")
                logger.warning("   2. Similarity threshold too high")
                logger.warning("   3. Query doesn't match any document content")
            
            # Build context from conversation history
            conversation_context = self.conversation_manager.get_conversation_context(
                user_phone_number=user_phone_number,
                session_id=session_id,
            )
            logger.info(f"   Conversation context: {len(conversation_context)} previous messages")
            
            # Generate response using LLM
            response = self._generate_response(
                query=query,
                relevant_chunks=relevant_chunks,
                conversation_context=conversation_context,
            )
            
            # Add assistant response to history
            self.conversation_manager.add_message(
                user_phone_number=user_phone_number,
                session_id=session_id,
                message_type="assistant",
                message=response,
                metadata={
                    "sources": [chunk.get("document_id") for chunk in relevant_chunks[:3]],
                    "num_chunks": len(relevant_chunks),
                },
            )
            
            logger.info(f"✅ RAG Query Complete")
            logger.info(f"   Response length: {len(response)} characters")
            logger.info(f"   Sources used: {[chunk.get('document_id') for chunk in relevant_chunks[:3]]}")
            logger.info("=" * 80)
            
            return {
                "response": response,
                "session_id": session_id,
                "sources": [chunk.get("document_id") for chunk in relevant_chunks[:3]],
                "num_sources": len(relevant_chunks),
            }
        except Exception as e:
            logger.error(f"Error processing RAG query: {str(e)}", exc_info=True)
            raise
    
    def _retrieve_relevant_chunks(self, query: str, user_phone_number: str,
                                  user_document_ids: List[int]) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks from vector store"""
        try:
            # Check if vector store has any vectors
            vector_count = self.vector_store.get_vector_count()
            logger.debug(f"FAISS vector store has {vector_count} vectors")
            
            if vector_count == 0:
                logger.warning("FAISS vector store is empty. No documents have been indexed.")
                return []
            
            # Generate query embedding
            query_embedding = self.embedding_service.embed(query)
            
            # Search vector store
            # Filter by user's accessible documents
            results = self.vector_store.search(
                query_vector=query_embedding,
                top_k=settings.RAG_TOP_K * 2,  # Get more to filter
            )
            
            logger.info(f"🔎 FAISS search returned {len(results)} results (before filtering)")
            logger.info(f"   Similarity threshold: {settings.RAG_SIMILARITY_THRESHOLD}")
            
            # Filter results by user's accessible documents and threshold
            relevant_chunks = []
            filtered_by_threshold = 0
            filtered_by_chunk_not_found = 0
            filtered_by_user_access = 0
            
            logger.info(f"📋 Processing {len(results)} FAISS results:")
            for i, (vector_id, similarity, metadata) in enumerate(results, 1):
                logger.info(f"   ┌─ Result {i}: {vector_id}")
                logger.info(f"   │  Similarity: {similarity:.4f} | Threshold: {settings.RAG_SIMILARITY_THRESHOLD}")
                logger.info(f"   │  Metadata: {metadata}")
                
                # Check similarity threshold
                if similarity < settings.RAG_SIMILARITY_THRESHOLD:
                    filtered_by_threshold += 1
                    logger.info(f"   └─ ❌ FILTERED: Similarity {similarity:.4f} < threshold {settings.RAG_SIMILARITY_THRESHOLD}")
                    continue
                else:
                    logger.info(f"   │  ✅ PASSED threshold check")
                
                # Get chunk from database
                chunk = self.chunk_repo.get_by_vector_id(vector_id)
                if not chunk:
                    filtered_by_chunk_not_found += 1
                    logger.warning(f"   └─ ❌ FILTERED: Chunk not found in database")
                    continue
                else:
                    logger.info(f"   │  ✅ Found chunk in DB: chunk_id={chunk.id}, document_id={chunk.document_id}")
                    logger.info(f"   │  Chunk text preview: {chunk.chunk_text[:100]}...")
                
                # Check if user has access to this document
                if chunk.user_phone_number:
                    # User-specific document - only accessible to that specific user
                    if chunk.user_phone_number != user_phone_number:
                        filtered_by_user_access += 1
                        logger.info(f"   └─ ❌ FILTERED: User access denied (chunk user: {chunk.user_phone_number}, query user: {user_phone_number})")
                        continue
                    else:
                        logger.info(f"   │  ✅ PASSED user access (user-specific document)")
                else:
                    # Global document (user_phone_number is NULL) - accessible to everyone
                    logger.info(f"   │  ✅ PASSED user access (global document)")
                
                # Add to relevant chunks
                chunk_info = {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "text": chunk.chunk_text,
                    "similarity": similarity,
                    "metadata": metadata,
                }
                relevant_chunks.append(chunk_info)
                logger.info(f"   └─ ✅ ADDED to relevant chunks (total: {len(relevant_chunks)})")
                
                if len(relevant_chunks) >= settings.RAG_TOP_K:
                    logger.info(f"   ⏹️  Reached max chunks limit ({settings.RAG_TOP_K}), stopping")
                    break
            
            logger.info(f"📊 Retrieval Summary:")
            logger.info(f"   - Total FAISS results: {len(results)}")
            logger.info(f"   - Filtered by threshold (< {settings.RAG_SIMILARITY_THRESHOLD}): {filtered_by_threshold}")
            logger.info(f"   - Filtered by chunk not found in DB: {filtered_by_chunk_not_found}")
            logger.info(f"   - Filtered by user access: {filtered_by_user_access}")
            logger.info(f"   - Final relevant chunks: {len(relevant_chunks)}")
            
            # Print all FAISS results for debugging (even filtered ones)
            if len(results) > 0:
                logger.info(f"🔎 All FAISS Search Results (before filtering):")
                for i, (vector_id, similarity, metadata) in enumerate(results[:10], 1):  # Show first 10
                    logger.info(f"   Result {i}:")
                    logger.info(f"      - Vector ID: {vector_id}")
                    logger.info(f"      - Similarity: {similarity:.4f}")
                    logger.info(f"      - Metadata: {metadata}")
            
            return relevant_chunks
        except Exception as e:
            logger.error(f"Error retrieving relevant chunks: {str(e)}", exc_info=True)
            return []
    
    def _generate_response(self, query: str, relevant_chunks: List[Dict[str, Any]],
                          conversation_context: List[Dict[str, str]]) -> str:
        """Generate response using LLM with retrieved context"""
        try:
            # Build context from retrieved chunks
            context_text = "\n\n".join([
                f"[Document {chunk['document_id']}]\n{chunk['text']}"
                for chunk in relevant_chunks
            ])
            
            # Build system prompt
            system_prompt = """You are a helpful assistant that answers questions based on the provided context documents.
Use only the information from the context to answer questions. If the context doesn't contain enough information,
say that you don't have enough information to answer the question.
Be concise and helpful in your responses."""
            
            # Build user prompt with context
            if context_text:
                user_prompt = f"""Context documents:
{context_text}

Question: {query}

Please answer the question based on the context provided above."""
            else:
                user_prompt = f"""Question: {query}

Note: No relevant context documents were found. Please answer based on your general knowledge, but mention that you don't have specific documents to reference."""
            
            # Prepare messages for LLM
            messages = []
            if conversation_context:
                messages.extend(conversation_context[:-1])  # All but last (current query)
            
            messages.append({"role": "user", "content": user_prompt})
            
            # Generate response
            if len(messages) > 1:
                response = self.llm_service.generate_with_context(messages)
            else:
                response = self.llm_service.generate(user_prompt, system_prompt=system_prompt)
            
            return response
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "I apologize, but I encountered an error while processing your question. Please try again."
    
    def _get_user_accessible_documents(self, user_phone_number: str) -> List[int]:
        """Get list of document IDs accessible to user (global + user-specific)"""
        try:
            # Get user-specific documents
            user_docs = self.user_doc_repo.get_user_documents(user_phone_number)
            document_ids = [ud.document_id for ud in user_docs]
            
            # Also include all global documents (where user_phone_number is NULL in chunks)
            # We'll handle this in the retrieval phase
            
            return document_ids
        except Exception as e:
            logger.error(f"Error getting user accessible documents: {str(e)}")
            return []
    
    def add_document(self, file_path: str, title: str, description: Optional[str] = None,
                    document_type: Optional[DocumentType] = None,
                    user_phone_number: Optional[str] = None,
                    created_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a document to the knowledge base
        
        Args:
            file_path: Path to the document file
            title: Document title
            description: Document description
            document_type: Document type (auto-detected if not provided)
            user_phone_number: If provided, make this a user-specific document
            created_by: User who added the document
            
        Returns:
            Dictionary with document info and processing status
        """
        try:
            # Detect document type
            if not document_type:
                file_ext = os.path.splitext(file_path)[1].lower()
                type_map = {
                    ".pdf": DocumentType.PDF,
                    ".docx": DocumentType.DOCX,
                    ".txt": DocumentType.TXT,
                    ".md": DocumentType.MD,
                    ".html": DocumentType.HTML,
                    ".csv": DocumentType.CSV,
                    ".xlsx": DocumentType.XLSX,
                    ".jpg": DocumentType.IMAGE,
                    ".jpeg": DocumentType.IMAGE,
                    ".png": DocumentType.IMAGE,
                }
                document_type = type_map.get(file_ext, DocumentType.OTHER)
            
            # Create document record
            doc = self.knowledge_doc_repo.create(
                title=title,
                description=description,
                document_type=document_type,
                file_path=file_path,
                status=DocumentStatus.PROCESSING,
                created_by=created_by,
            )
            
            # Process document asynchronously (for now, we'll do it synchronously)
            try:
                # Extract text
                processed = self.document_processor.process_file(file_path)
                text = processed.get("text", "")
                
                if not text:
                    raise ValueError("No text extracted from document")
                
                logger.info(f"📄 Extracted {len(text)} characters from document")
                
                # Enhance text using LLM (if enabled)
                enhanced_text = self.text_enhancer.enhance_text(
                    text=text,
                    document_title=title,
                    document_type=document_type.value if document_type else None
                )
                
                if enhanced_text != text:
                    logger.info(f"✨ Text enhanced: {len(text)} → {len(enhanced_text)} characters")
                    text = enhanced_text
                else:
                    logger.info("ℹ️  Text enhancement skipped or unchanged")
                
                # Chunk text using LangChain
                chunks = self.document_processor.chunk_text(text, title=title)
                
                # Generate embeddings and add to vector store
                chunk_texts = [chunk["text"] for chunk in chunks]
                embeddings = self.embedding_service.embed_batch(chunk_texts)
                
                # Add to vector store and database
                vector_ids = []
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    vector_id = f"doc_{doc.id}_chunk_{i}_{uuid.uuid4().hex[:8]}"
                    vector_ids.append(vector_id)
                    
                    # Create chunk record
                    chunk_record = self.chunk_repo.create(
                        document_id=doc.id,
                        chunk_index=chunk["chunk_index"],
                        chunk_text=chunk["text"],
                        chunk_start=chunk.get("start"),
                        chunk_end=chunk.get("end"),
                        user_phone_number=user_phone_number,
                        vector_id=vector_id,
                    )
                
                # Add vectors to vector store
                metadata_list = [
                    {
                        "document_id": doc.id,
                        "chunk_index": chunk["chunk_index"],
                        "user_phone_number": user_phone_number,
                    }
                    for chunk in chunks
                ]
                self.vector_store.add_vectors(embeddings, vector_ids, metadata_list)
                self.vector_store.save()
                
                # Update document status
                self.knowledge_doc_repo.update(
                    doc.id,
                    status=DocumentStatus.COMPLETED,
                    processed_at=datetime.utcnow(),
                )
                
                logger.info(f"✅ Successfully processed document {doc.id}: {title}")
                
                return {
                    "document_id": doc.id,
                    "title": title,
                    "status": "completed",
                    "num_chunks": len(chunks),
                }
            except Exception as e:
                # Update document status to failed
                self.knowledge_doc_repo.update(
                    doc.id,
                    status=DocumentStatus.FAILED,
                    error_message=str(e),
                )
                logger.error(f"❌ Failed to process document {doc.id}: {str(e)}")
                raise
        
        except Exception as e:
            logger.error(f"Error adding document: {str(e)}")
            raise
    
    def add_website(self, url: str, title: Optional[str] = None,
                   user_phone_number: Optional[str] = None,
                   created_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a website to the knowledge base
        
        Args:
            url: URL to scrape
            title: Optional title (auto-generated if not provided)
            user_phone_number: If provided, make this a user-specific document
            created_by: User who added the website
            
        Returns:
            Dictionary with document info and processing status
        """
        try:
            # Scrape website
            scraped = self.website_scraper.scrape_url(url)
            
            # Enhance scraped text using LLM
            scraped_text = scraped.get("text", "")
            if scraped_text:
                logger.info(f"📄 Scraped {len(scraped_text)} characters from website")
                enhanced_text = self.text_enhancer.enhance_text(
                    text=scraped_text,
                    document_title=title or scraped.get("title", url),
                    document_type="website"
                )
                if enhanced_text != scraped_text:
                    logger.info(f"✨ Scraped text enhanced: {len(scraped_text)} → {len(enhanced_text)} characters")
                    scraped["text"] = enhanced_text
            
            # Save scraped content to a temporary file
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
            temp_file.write(scraped["text"])
            temp_file.close()
            
            # Use add_document with the scraped content
            title = title or scraped.get("title", url)
            result = self.add_document(
                file_path=temp_file.name,
                title=title,
                description=scraped.get("description"),
                document_type=DocumentType.WEBSITE,
                user_phone_number=user_phone_number,
                created_by=created_by,
            )
            
            # Update document with source URL
            self.knowledge_doc_repo.update(
                result["document_id"],
                source_url=url,
            )
            
            # Clean up temp file
            os.unlink(temp_file.name)
            
            return result
        except ValueError as e:
            # Handle authentication errors
            if "authentication" in str(e).lower() or "forbidden" in str(e).lower():
                raise ValueError(f"Cannot scrape website: {str(e)}. Please provide a publicly accessible URL.")
            raise
        except Exception as e:
            logger.error(f"Error adding website: {str(e)}")
            raise
