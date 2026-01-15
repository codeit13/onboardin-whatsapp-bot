"""
RAG API endpoints
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.config import get_settings
from app.services.rag.rag_service import RAGService
from app.tables.knowledge_documents import KnowledgeDocumentRepository, DocumentType, DocumentStatus
from app.tables.user_documents import UserDocumentRepository
from app.tables.users import UserRepository
from app.tables.document_chunks import DocumentChunkRepository

settings = get_settings()

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response models
class ChatRequest(BaseModel):
    query: str = Field(..., description="User's query/question")
    session_id: Optional[str] = Field(None, description="Optional session ID")


class ChatResponse(BaseModel):
    response: str
    session_id: str
    sources: List[int]
    num_sources: int


class ChunkResponse(BaseModel):
    id: int
    chunk_index: int
    chunk_text: str
    chunk_start: Optional[int]
    chunk_end: Optional[int]
    vector_id: Optional[str]
    created_at: str


class DocumentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    document_type: str
    status: str
    created_at: str
    processed_at: Optional[str]
    chunks: List[ChunkResponse] = []


class UserDocumentMappingRequest(BaseModel):
    user_phone_number: str
    document_id: int
    assigned_by: Optional[str] = None
    notes: Optional[str] = None


@router.post("/chat", response_model=ChatResponse, tags=["rag"])
async def chat(
    request: ChatRequest,
    phone_number: str = Query(..., description="User's phone number"),
    db: Session = Depends(get_db),
):
    """
    Chat with RAG chatbot
    
    Args:
        request: Chat request with query
        phone_number: User's phone number (from form or header)
        db: Database session
        
    Returns:
        Chat response with answer and sources
    """
    try:
        # Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_phone(phone_number)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with phone number {phone_number} not found"
            )
        
        # Initialize RAG service
        rag_service = RAGService(db)
        
        # Process query
        result = rag_service.query(
            user_phone_number=phone_number,
            query=request.query,
            session_id=request.session_id,
        )
        
        return ChatResponse(
            response=result["response"],
            session_id=result["session_id"],
            sources=result.get("sources", []),
            num_sources=result.get("num_sources", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}"
        )


@router.post("/documents", response_model=List[DocumentResponse], tags=["rag"])
async def upload_document(
    files: List[UploadFile] = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    user_phone_number: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload one or more documents to the knowledge base
    
    Args:
        files: One or more document files to upload
        title: Document title (ignored when uploading multiple files, used as fallback for single file if provided)
        description: Document description (applied to all files)
        user_phone_number: If provided, make this user-specific
        created_by: User who uploaded the document
        db: Database session
        
    Returns:
        List of document information
    """
    try:
        import os
        from app.core.config import get_settings
        
        settings = get_settings()
        os.makedirs(settings.DOCUMENTS_STORAGE_PATH, exist_ok=True)
        
        # Determine if we're handling multiple files
        is_multiple_files = len(files) > 1
        
        # If multiple files, ignore title field
        if is_multiple_files:
            title = None
        
        documents = []
        rag_service = RAGService(db)
        doc_repo = KnowledgeDocumentRepository(db)
        chunk_repo = DocumentChunkRepository(db)
        
        for file in files:
            # Save uploaded file
            file_path = os.path.join(settings.DOCUMENTS_STORAGE_PATH, file.filename)
            
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Determine title: use filename if title is empty/None, otherwise use provided title
            # For multiple files, always use filename
            document_title = file.filename if (is_multiple_files or not title or title.strip() == "") else title
            
            # Initialize RAG service and add document
            result = rag_service.add_document(
                file_path=file_path,
                title=document_title,
                description=description,
                user_phone_number=user_phone_number,
                created_by=created_by,
            )
            
            # Get document details
            doc = doc_repo.get_by_id(result["document_id"])
            
            # Get all chunks for this document
            chunks = chunk_repo.get_by_document(doc.id, user_phone_number=user_phone_number)
            
            # Convert chunks to response format
            chunk_responses = [
                ChunkResponse(
                    id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.chunk_text,
                    chunk_start=chunk.chunk_start,
                    chunk_end=chunk.chunk_end,
                    vector_id=chunk.vector_id,
                    created_at=chunk.created_at.isoformat() if chunk.created_at else "",
                )
                for chunk in chunks
            ]
            
            documents.append(DocumentResponse(
                id=doc.id,
                title=doc.title,
                description=doc.description,
                document_type=doc.document_type.value if doc.document_type else "unknown",
                status=doc.status.value if doc.status else "unknown",
                created_at=doc.created_at.isoformat() if doc.created_at else "",
                processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
                chunks=chunk_responses,
            ))
        
        return documents
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading document: {str(e)}"
        )


@router.post("/websites", response_model=DocumentResponse, tags=["rag"])
async def add_website(
    url: str = Form(...),
    title: Optional[str] = Form(None),
    user_phone_number: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Add a website to the knowledge base
    
    Args:
        url: URL to scrape
        title: Optional title
        user_phone_number: If provided, make this user-specific
        created_by: User who added the website
        db: Database session
        
    Returns:
        Document information
    """
    try:
        # Initialize RAG service and add website
        rag_service = RAGService(db)
        result = rag_service.add_website(
            url=url,
            title=title,
            user_phone_number=user_phone_number,
            created_by=created_by,
        )
        
        # Get document details
        doc_repo = KnowledgeDocumentRepository(db)
        doc = doc_repo.get_by_id(result["document_id"])
        
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            description=doc.description,
            document_type=doc.document_type.value if doc.document_type else "unknown",
            status=doc.status.value if doc.status else "unknown",
            created_at=doc.created_at.isoformat() if doc.created_at else "",
            processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
        )
    except ValueError as e:
        # Handle authentication/access errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error adding website: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding website: {str(e)}"
        )


@router.get("/documents", response_model=List[DocumentResponse], tags=["rag"])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List all knowledge base documents
    
    Args:
        skip: Number of documents to skip
        limit: Maximum number of documents to return
        status_filter: Filter by status (pending, processing, completed, failed)
        document_type: Filter by document type
        db: Database session
        
    Returns:
        List of documents
    """
    try:
        doc_repo = KnowledgeDocumentRepository(db)
        
        status_enum = None
        if status_filter:
            try:
                status_enum = DocumentStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}"
                )
        
        type_enum = None
        if document_type:
            try:
                type_enum = DocumentType(document_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid document type: {document_type}"
                )
        
        docs = doc_repo.list_all(
            skip=skip,
            limit=limit,
            status=status_enum,
            document_type=type_enum,
        )
        
        return [
            DocumentResponse(
                id=doc.id,
                title=doc.title,
                description=doc.description,
                document_type=doc.document_type.value if doc.document_type else "unknown",
                status=doc.status.value if doc.status else "unknown",
                created_at=doc.created_at.isoformat() if doc.created_at else "",
                processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
            )
            for doc in docs
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing documents: {str(e)}"
        )


@router.get("/documents/{document_id}", response_model=DocumentResponse, tags=["rag"])
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific document by ID"""
    try:
        doc_repo = KnowledgeDocumentRepository(db)
        doc = doc_repo.get_by_id(document_id)
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            description=doc.description,
            document_type=doc.document_type.value if doc.document_type else "unknown",
            status=doc.status.value if doc.status else "unknown",
            created_at=doc.created_at.isoformat() if doc.created_at else "",
            processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting document: {str(e)}"
        )


@router.delete("/documents/{document_id}", tags=["rag"])
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    """Delete a document from the knowledge base"""
    try:
        doc_repo = KnowledgeDocumentRepository(db)
        doc = doc_repo.get_by_id(document_id)
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        # Delete chunks from vector store
        from app.tables.document_chunks import DocumentChunkRepository
        chunk_repo = DocumentChunkRepository(db)
        chunks = chunk_repo.get_by_document(document_id)
        
        if chunks:
            from app.services.rag.vector_store import get_vector_store
            from app.services.rag.embedding_service import get_embedding_service
            embedding_service = get_embedding_service()
            vector_store = get_vector_store(dimension=embedding_service.dimension)
            
            vector_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]
            if vector_ids:
                vector_store.delete_vectors(vector_ids)
                vector_store.save()
        
        # Delete chunks from database
        chunk_repo.delete_by_document(document_id)
        
        # Delete document
        doc_repo.delete(document_id)
        
        return {"message": f"Document {document_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting document: {str(e)}"
        )


@router.post("/user-documents", tags=["rag"])
async def assign_document_to_user(
    request: UserDocumentMappingRequest,
    db: Session = Depends(get_db),
):
    """
    Assign a document to a user (HR function)
    
    Args:
        request: User document mapping request
        db: Database session
        
    Returns:
        Mapping information
    """
    try:
        # Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_phone(request.user_phone_number)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with phone number {request.user_phone_number} not found"
            )
        
        # Verify document exists
        doc_repo = KnowledgeDocumentRepository(db)
        doc = doc_repo.get_by_id(request.document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {request.document_id} not found"
            )
        
        # Create mapping
        user_doc_repo = UserDocumentRepository(db)
        mapping = user_doc_repo.create(
            user_phone_number=request.user_phone_number,
            document_id=request.document_id,
            assigned_by=request.assigned_by,
            notes=request.notes,
        )
        
        return {
            "id": mapping.id,
            "user_phone_number": mapping.user_phone_number,
            "document_id": mapping.document_id,
            "assigned_by": mapping.assigned_by,
            "notes": mapping.notes,
            "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning document to user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assigning document: {str(e)}"
        )


@router.get("/user-documents/{user_phone_number}", tags=["rag"])
async def get_user_documents(
    user_phone_number: str,
    db: Session = Depends(get_db),
):
    """Get all documents assigned to a user"""
    try:
        user_doc_repo = UserDocumentRepository(db)
        mappings = user_doc_repo.get_user_documents(user_phone_number)
        
        doc_repo = KnowledgeDocumentRepository(db)
        documents = []
        for mapping in mappings:
            doc = doc_repo.get_by_id(mapping.document_id)
            if doc:
                documents.append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "description": doc.description,
                    "document_type": doc.document_type.value if doc.document_type else "unknown",
                    "assigned_by": mapping.assigned_by,
                    "notes": mapping.notes,
                    "assigned_at": mapping.created_at.isoformat() if mapping.created_at else None,
                })
        
        return {"user_phone_number": user_phone_number, "documents": documents}
    except Exception as e:
        logger.error(f"Error getting user documents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user documents: {str(e)}"
        )


@router.delete("/user-documents/{mapping_id}", tags=["rag"])
async def unassign_document_from_user(
    mapping_id: int,
    db: Session = Depends(get_db),
):
    """Remove a document assignment from a user"""
    try:
        user_doc_repo = UserDocumentRepository(db)
        success = user_doc_repo.delete(mapping_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User document mapping {mapping_id} not found"
            )
        
        return {"message": f"Document assignment {mapping_id} removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unassigning document: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error unassigning document: {str(e)}"
        )


@router.get("/diagnostics", tags=["rag"])
async def rag_diagnostics(
    db: Session = Depends(get_db),
):
    """Diagnostic endpoint to check RAG system status"""
    try:
        from app.services.rag.singletons import get_vector_store_instance, get_embedding_service_instance
        from app.tables.document_chunks import DocumentChunkRepository
        from app.tables.knowledge_documents import KnowledgeDocumentRepository
        
        # Get counts
        doc_repo = KnowledgeDocumentRepository(db)
        chunk_repo = DocumentChunkRepository(db)
        
        all_docs = doc_repo.list_all(limit=1000)
        total_docs = len(all_docs)
        completed_docs = len([d for d in all_docs if d.status == DocumentStatus.COMPLETED])
        
        # Get chunk counts
        total_chunks = 0
        chunks_by_doc = {}
        for doc in all_docs:
            chunks = chunk_repo.get_by_document(doc.id)
            chunk_count = len(chunks)
            total_chunks += chunk_count
            chunks_by_doc[doc.id] = {
                "title": doc.title,
                "chunks": chunk_count,
                "status": doc.status.value if doc.status else "unknown"
            }
        
        # Get FAISS vector count
        try:
            vector_store = get_vector_store_instance()
            faiss_vector_count = vector_store.get_vector_count()
        except Exception as e:
            faiss_vector_count = f"Error: {str(e)}"
        
        # Get embedding service status
        try:
            embedding_service = get_embedding_service_instance()
            embedding_dim = embedding_service.dimension
            embedding_loaded = True
        except Exception as e:
            embedding_dim = None
            embedding_loaded = False
        
        return {
            "database": {
                "total_documents": total_docs,
                "completed_documents": completed_docs,
                "total_chunks": total_chunks,
                "documents_detail": chunks_by_doc
            },
            "faiss": {
                "vector_count": faiss_vector_count,
                "index_path": getattr(getattr(settings, 'VECTOR_STORE_PATH', None), 'VECTOR_STORE_PATH', './data/vector_store')
            },
            "embedding_service": {
                "loaded": embedding_loaded,
                "dimension": embedding_dim
            },
            "status": "healthy" if (completed_docs > 0 and total_chunks > 0) else "no_documents_indexed"
        }
    except Exception as e:
        logger.error(f"Error in diagnostics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting diagnostics: {str(e)}"
        )
