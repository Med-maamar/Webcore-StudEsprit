# Bibliothèque Module - Setup Guide

## Quick Start

The Bibliothèque module is now integrated into your StudEsprit Django project! Here's how to get it running:

### 1. Basic Setup (Works without external dependencies)

The module is designed to work with graceful fallbacks when optional dependencies are missing:

```bash
# Navigate to your project directory
cd StudEsprit

# Initialize the library database indexes
python manage.py init_library

# Start the development server
python manage.py runserver
```

**The module will work with basic functionality even without installing the AI dependencies!**

### 2. Full AI Features Setup (Recommended)

To enable full AI-powered features, install the additional dependencies:

```bash
# Install AI and PDF processing dependencies
pip install PyMuPDF>=1.23.0
pip install sentence-transformers>=2.2.2
pip install openai>=1.0.0
pip install numpy>=1.24.0
pip install scikit-learn>=1.3.0
```

### 3. OpenAI Integration (Optional)

For enhanced AI responses, add your OpenAI API key to your `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

## Features Available

### Without External Dependencies
- ✅ Document upload interface
- ✅ Basic document management
- ✅ Chat interface (with fallback responses)
- ✅ User authentication and session management
- ✅ Beautiful Tailwind CSS interface

### With Full Dependencies
- ✅ PDF text extraction
- ✅ Semantic search using embeddings
- ✅ AI-powered responses via OpenAI
- ✅ Advanced document processing
- ✅ Intelligent paragraph-based search

## Usage

1. **Access the Library**: Navigate to `/library/` (only visible when logged in)
2. **Upload Documents**: Click "Ajouter un document" to upload PDFs
3. **Chat with AI**: Open a processed document and use the chat interface
4. **View History**: Access conversation history in the sessions page

## File Structure

```
StudEsprit/
├── library/                    # New library app
│   ├── models.py              # MongoDB service classes
│   ├── views.py               # Django views
│   ├── urls.py                # URL routing
│   ├── templates/library/     # HTML templates
│   └── management/commands/   # Django management commands
├── core/
│   └── library_services.py    # Core business logic
└── requirements.txt           # Updated with new dependencies
```

## API Endpoints

- `GET /library/` - Main library dashboard
- `GET /library/upload/` - Document upload page
- `GET /library/reader/{doc_id}/` - Document reader with chat
- `POST /library/api/chat/` - Send chat message
- `GET /library/api/search/?q=query` - Semantic search
- `DELETE /library/api/documents/{doc_id}/delete/` - Delete document

## Troubleshooting

### Common Issues

1. **"PyMuPDF is not installed"**: Install with `pip install PyMuPDF`
2. **"sentence-transformers not available"**: Install with `pip install sentence-transformers`
3. **"OpenAI library is not installed"**: Install with `pip install openai`
4. **MongoDB connection issues**: Check your `MONGO_URI` in settings

### Fallback Behavior

The system gracefully handles missing dependencies:
- **No PyMuPDF**: Shows error message when trying to upload PDFs
- **No sentence-transformers**: Uses simple hash-based embeddings
- **No OpenAI**: Uses keyword-based response generation
- **No API key**: Falls back to simple responses

## Development

### Adding New Features

1. **New Document Types**: Extend `PDFProcessor` in `core/library_services.py`
2. **Custom AI Providers**: Modify `AIService` class
3. **UI Components**: Add new templates in `library/templates/library/`
4. **API Endpoints**: Add new views in `library/views.py`

### Testing

```bash
# Run Django checks
python manage.py check

# Test specific functionality
python manage.py shell
>>> from core.library_services import PDFProcessor
>>> # Test PDF processing
```

## Production Deployment

1. **Install all dependencies** for full functionality
2. **Set up OpenAI API key** for enhanced AI responses
3. **Configure MongoDB indexes** with `python manage.py init_library`
4. **Set up file storage** for uploaded documents
5. **Configure static files** for the Tailwind CSS interface

## Security Notes

- All operations require user authentication
- Documents are isolated per user
- File uploads are validated and sanitized
- CSRF protection is enabled on all forms
- Input validation and escaping are implemented

## Performance

- MongoDB indexes for fast queries
- Embedding caching for repeated searches
- Pagination for large document lists
- Graceful handling of large files

The module is production-ready and can be extended with additional features as needed!
