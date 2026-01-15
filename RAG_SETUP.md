# RAG Chatbot Setup Guide

This guide explains how to set up and use the RAG (Retrieval-Augmented Generation) chatbot system in this project.

## Overview

The RAG chatbot is a separate, independent module that can be used by:
- WhatsApp integration (via Twilio)
- Custom UI applications
- Direct API calls

## Features

- **Multi-format document support**: PDF, DOCX, TXT, Markdown, HTML, CSV, Excel, Images (with OCR)
- **Website scraping**: Add websites to knowledge base
- **User-specific documents**: HR can assign documents to specific users
- **Conversation history**: Maintains context across chat sessions
- **Dynamic model selection**: LLM and embedding models can be changed via configuration
- **Vector search**: FAISS-based semantic search for relevant information

## Prerequisites

1. **MySQL Database**: Set up MySQL and configure `DATABASE_URL` in `.env`
2. **Python Dependencies**: Install all requirements (see below)
3. **API Keys**: 
   - Gemini API key for LLM (or configure another provider)
   - Tesseract OCR (for image processing)

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Tesseract OCR (for image processing)

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

### 3. Configure Environment Variables

Add to your `.env` file:

```env
# Database
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/onboarding_db

# RAG Configuration
LLM_PROVIDER=gemini
LLM_API_KEY=your_gemini_api_key_here
LLM_MODEL_NAME=gemini-pro  # Optional, defaults to gemini-pro
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048

# Embeddings
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2  # Default model

# Vector Store
VECTOR_STORE_TYPE=faiss
VECTOR_STORE_PATH=./data/vector_store
VECTOR_DIMENSION=384  # For all-MiniLM-L6-v2

# RAG Settings
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7

# Document Storage
DOCUMENTS_STORAGE_PATH=./data/documents
OCR_ENABLED=true
OCR_LANGUAGE=eng

# Conversation Settings
CONVERSATION_HISTORY_LIMIT=10
SESSION_TIMEOUT_HOURS=24
```

### 4. Initialize Database

The database tables will be created automatically on startup. Alternatively, you can create them manually:

```python
from app.core.database import init_database, create_tables
init_database()
create_tables()
```

## Usage

### API Endpoints

#### 1. Chat with RAG

```bash
POST /api/v1/rag/chat?phone_number=+1234567890
Content-Type: application/json

{
  "query": "What is the company policy on remote work?",
  "session_id": "optional_session_id"
}
```

Response:
```json
{
  "response": "Based on the company policy documents...",
  "session_id": "session_+1234567890",
  "sources": [1, 2, 3],
  "num_sources": 3
}
```

#### 2. Upload Document

```bash
POST /api/v1/rag/documents
Content-Type: multipart/form-data

file: <file>
title: "Company Policy Document"
description: "Remote work policy"
user_phone_number: "+1234567890"  # Optional, for user-specific docs
created_by: "admin"
```

#### 3. Add Website

```bash
POST /api/v1/rag/websites
Content-Type: multipart/form-data

url: "https://example.com/policy"
title: "Company Policy Page"  # Optional
user_phone_number: "+1234567890"  # Optional
created_by: "admin"
```

#### 4. List Documents

```bash
GET /api/v1/rag/documents?skip=0&limit=100&status_filter=completed
```

#### 5. Assign Document to User (HR Function)

```bash
POST /api/v1/rag/user-documents
Content-Type: application/json

{
  "user_phone_number": "+1234567890",
  "document_id": 1,
  "assigned_by": "hr@company.com",
  "notes": "Required reading for new employees"
}
```

### WhatsApp Integration

The RAG system is automatically integrated with WhatsApp. When a user sends a message via WhatsApp:

1. The webhook receives the message
2. A Celery task processes it
3. The task calls the RAG service
4. RAG retrieves relevant information and generates a response
5. Response is sent back via WhatsApp

No additional configuration needed - it works automatically!

## Architecture

### Database Tables

- **users**: User information (phone number as primary key)
- **knowledge_documents**: Company-wide knowledge base documents
- **user_documents**: Mapping of documents to users (for user-specific docs)
- **conversation_history**: Chat history for context/memory
- **document_chunks**: Metadata about document chunks in vector store

### Services

- **LLMService**: Abstracted LLM provider (Gemini, OpenAI, etc.)
- **EmbeddingService**: Abstracted embedding provider (sentence-transformers, etc.)
- **VectorStore**: Abstracted vector database (FAISS, Pinecone, etc.)
- **DocumentProcessor**: Handles various document formats and OCR
- **WebsiteScraper**: Scrapes website content
- **ConversationManager**: Manages conversation history
- **RAGService**: Main orchestration service

## Customization

### Changing LLM Provider

Update `.env`:
```env
LLM_PROVIDER=openai  # or anthropic, etc.
LLM_API_KEY=your_openai_key
LLM_MODEL_NAME=gpt-4
```

Then implement the provider in `app/services/rag/llm_service.py`.

### Changing Embedding Model

Update `.env`:
```env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL_NAME=all-mpnet-base-v2  # Better but slower
VECTOR_DIMENSION=768  # Update dimension for new model
```

### Changing Vector Store

Update `.env`:
```env
VECTOR_STORE_TYPE=pinecone  # or weaviate, qdrant, etc.
```

Then implement the provider in `app/services/rag/vector_store.py`.

## Troubleshooting

### Database Connection Issues

- Verify `DATABASE_URL` is correct
- Ensure MySQL is running
- Check database user permissions

### OCR Not Working

- Verify Tesseract is installed: `tesseract --version`
- Check `OCR_ENABLED=true` in `.env`
- For other languages, update `OCR_LANGUAGE` (e.g., `fra` for French)

### Vector Store Issues

- Ensure `VECTOR_STORE_PATH` directory exists and is writable
- Check disk space for FAISS index files
- If index is corrupted, delete `.index` and `.metadata` files to rebuild

### Low Quality Responses

- Add more relevant documents to knowledge base
- Adjust `RAG_TOP_K` to retrieve more chunks
- Lower `RAG_SIMILARITY_THRESHOLD` to include more results
- Increase `RAG_CHUNK_SIZE` for better context

## Future Enhancements

- [ ] S3 storage for documents
- [ ] Support for more LLM providers (OpenAI, Anthropic)
- [ ] Support for more vector stores (Pinecone, Weaviate, Qdrant)
- [ ] Streaming responses for custom UI
- [ ] Document versioning
- [ ] Advanced chunking strategies
- [ ] Multi-language support
