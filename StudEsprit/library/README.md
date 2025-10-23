# Bibliothèque Module - StudEsprit

## Overview

The Bibliothèque module provides an AI-powered document management and chat system for the StudEsprit platform. Users can upload PDF documents, extract text content, and interact with an AI assistant that can answer questions based on the document content using semantic search.

## Features

- **PDF Upload & Processing**: Upload PDF documents with automatic text extraction
- **AI Chat Interface**: Interactive chat with AI assistant based on document content
- **Semantic Search**: Find relevant information using embeddings and similarity search
- **Session Management**: Maintain conversation history per user and document
- **User Authentication**: Role-based access (STUDENT, TEACHER, ADMIN)
- **Modern UI**: Beautiful interface built with Tailwind CSS

## Architecture

### Models (MongoDB Collections)

- **documents**: Store PDF metadata, extracted content, and embeddings
- **chat_sessions**: Manage conversation history and context
- **users**: User authentication and role management (existing)

### Services

- **PDFProcessor**: Extract text from PDF files using PyMuPDF
- **EmbeddingProcessor**: Generate embeddings using sentence-transformers
- **AIService**: Generate responses using OpenAI API or fallback methods
- **SemanticSearchService**: Perform semantic search across documents
- **DocumentService**: CRUD operations for documents
- **ChatService**: Manage chat sessions and messages

### Views

- **library_home**: Main dashboard showing user documents
- **upload_document**: PDF upload interface
- **document_reader**: Chat interface with document content
- **chat_message**: API endpoint for chat interactions
- **search_documents**: Semantic search API
- **chat_sessions**: View conversation history

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

The following packages are required:
- PyMuPDF>=1.23.0 (PDF processing)
- sentence-transformers>=2.2.2 (embeddings)
- openai>=1.0.0 (AI responses)
- numpy>=1.24.0
- scikit-learn>=1.3.0

### 2. Environment Variables

Add to your `.env` file:

```env
# OpenAI API (optional - fallback available)
OPENAI_API_KEY=your_openai_api_key_here

# MongoDB (existing)
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=studesprit
```

### 3. Initialize Database

```bash
python manage.py init_library
```

This command creates the necessary MongoDB indexes for optimal performance.

### 4. Run the Application

```bash
python manage.py runserver
```

## Usage

### For Users

1. **Upload Documents**: Navigate to `/library/` and click "Ajouter un document"
2. **Chat with AI**: Open a processed document and use the chat interface
3. **View History**: Access conversation history in the sessions page

### For Developers

#### Adding New Features

1. **New Document Types**: Extend `PDFProcessor` to support other formats
2. **Custom Embeddings**: Modify `EmbeddingProcessor` to use different models
3. **AI Providers**: Add new providers in `AIService`
4. **UI Components**: Extend templates with new Tailwind components

#### API Endpoints

- `POST /library/api/chat/` - Send chat message
- `GET /library/api/chat/{session_id}/history/` - Get chat history
- `GET /library/api/search/?q=query` - Semantic search
- `DELETE /library/api/documents/{doc_id}/delete/` - Delete document
- `DELETE /library/api/sessions/{session_id}/delete/` - Delete session

## File Structure

```
library/
├── __init__.py
├── apps.py
├── models.py              # MongoDB service classes
├── views.py               # Django views
├── urls.py                # URL routing
├── management/
│   └── commands/
│       └── init_library.py
└── templates/
    └── library/
        ├── home.html      # Document dashboard
        ├── upload.html    # Upload interface
        ├── reader.html    # Chat interface
        └── chat_sessions.html

core/
└── library_services.py    # Core business logic
```

## Configuration

### OpenAI Integration

The system supports OpenAI GPT models for enhanced AI responses. If no API key is provided, it falls back to a simple keyword-based response system.

### Embedding Models

Default model: `all-MiniLM-L6-v2` (384 dimensions)
- Lightweight and fast
- Good performance for most use cases
- Can be changed in `get_embedding_model()`

### File Limits

- Maximum file size: 10MB
- Supported formats: PDF only
- Processing timeout: Handled gracefully with user feedback

## Security

- User authentication required for all operations
- Documents are isolated per user
- File upload validation and sanitization
- CSRF protection on all forms
- Input validation and escaping

## Performance

- MongoDB indexes for fast queries
- Embedding caching for repeated searches
- Pagination for large document lists
- Async processing for large files (can be extended with Celery)

## Troubleshooting

### Common Issues

1. **PDF Processing Fails**: Check file format and size limits
2. **Embeddings Not Generated**: Verify sentence-transformers installation
3. **AI Responses Slow**: Check OpenAI API key and rate limits
4. **MongoDB Connection**: Verify MONGO_URI and database access

### Debug Mode

Enable Django debug mode to see detailed error messages and logs.

## Future Enhancements

- [ ] Support for more document formats (DOCX, TXT, etc.)
- [ ] Batch document processing with Celery
- [ ] Advanced search filters and sorting
- [ ] Document sharing between users
- [ ] Export chat conversations
- [ ] Multi-language support
- [ ] Advanced AI features (summarization, Q&A generation)
- [ ] Document versioning and history
- [ ] Integration with external document sources

## Contributing

1. Follow the existing code structure and patterns
2. Add appropriate error handling and logging
3. Update documentation for new features
4. Test with various PDF formats and sizes
5. Ensure responsive design for mobile devices
