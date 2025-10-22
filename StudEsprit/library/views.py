"""
Views for the Library module including document upload, chat interface, and semantic search.
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib import messages
from django.core.paginator import Paginator
from django.conf import settings

from core.decorators import login_required_mongo
from django.http import HttpResponse
from library.models import DocumentService, ChatService, EmbeddingService, CommunityService
from core.library_services import (
    PDFProcessor, EmbeddingProcessor, AIService, 
    SemanticSearchService, process_uploaded_document
)

logger = logging.getLogger(__name__)


def library_test(request):
    """Test endpoint to verify library module is working."""
    return HttpResponse("""
    <html>
    <head>
        <title>Bibliothèque - Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
            .info { color: #6c757d; margin-bottom: 15px; }
            .btn { display: inline-block; padding: 10px 20px; background: #c8102e; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }
            .btn:hover { background: #a00d26; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success">✅ Bibliothèque Module is Working!</div>
            <div class="info">The Bibliothèque module has been successfully integrated into your StudEsprit project.</div>
            <div class="info">To access the full functionality, please log in to your account.</div>
            <a href="/auth/login" class="btn">Login</a>
            <a href="/auth/register" class="btn">Register</a>
            <a href="/" class="btn">Home</a>
        </div>
    </body>
    </html>
    """)


@login_required_mongo
def library_home(request):
    """Main library page showing user's documents."""
    user_id = request.user.id
    page = int(request.GET.get('page', 1))
    page_size = 10
    
    documents, total = DocumentService.get_user_documents(user_id, page, page_size)
    
    # Convert MongoDB _id to id for template compatibility
    for doc in documents:
        doc['id'] = str(doc['_id'])
    
    # Add pagination
    paginator = Paginator(range(total), page_size)
    page_obj = paginator.get_page(page)
    
    context = {
        'documents': documents,
        'page_obj': page_obj,
        'total_documents': total
    }
    
    return render(request, 'library/home.html', context)


@login_required_mongo
def upload_document(request):
    """Handle PDF document upload."""
    if request.method == 'GET':
        return render(request, 'library/upload.html')
    
    if request.method == 'POST':
        try:
            if 'pdf_file' not in request.FILES:
                messages.error(request, 'No file selected.')
                return redirect('library:upload')
            
            pdf_file = request.FILES['pdf_file']
            
            # Validate file type
            if not pdf_file.name.lower().endswith('.pdf'):
                messages.error(request, 'Please upload a PDF file.')
                return redirect('library:upload')
            
            # Validate file size (10MB limit)
            if pdf_file.size > 10 * 1024 * 1024:
                messages.error(request, 'File size must be less than 10MB.')
                return redirect('library:upload')
            
            # Save file
            file_path = default_storage.save(
                f'documents/{request.user.id}/{pdf_file.name}',
                ContentFile(pdf_file.read())
            )
            
            # Create document record
            doc_id = DocumentService.create_document(
                user_id=request.user.id,
                title=request.POST.get('title', pdf_file.name),
                filename=pdf_file.name,
                file_path=file_path,
                file_size=pdf_file.size,
                content="",  # Will be filled during processing
                metadata={}
            )
            
            # Process document asynchronously (in a real app, use Celery)
            try:
                full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
                success = process_uploaded_document(full_file_path, doc_id)
                
                if success:
                    messages.success(request, 'Document uploaded and processed successfully!')
                else:
                    messages.warning(request, 'Document uploaded but processing failed. Please try again.')
            except Exception as e:
                logger.error(f"Error processing document: {e}")
                messages.warning(request, 'Document uploaded but processing failed. Please try again.')
            
            return redirect('library:home')
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            messages.error(request, 'An error occurred while uploading the document.')
            return redirect('library:upload')


@login_required_mongo
def document_reader(request, doc_id):
    """Document reader page with chat interface."""
    user_id = request.user.id
    
    # Get document
    document = DocumentService.get_document_by_id(doc_id)
    if not document or str(document['user_id']) != user_id:
        messages.error(request, 'Document not found or access denied.')
        return redirect('library:home')
    
    # Convert MongoDB _id to id for template compatibility
    document['id'] = str(document['_id'])
    
    # Get or create chat session for this document
    session_id = request.GET.get('session_id')
    if session_id:
        chat_session = ChatService.get_chat_session(session_id, user_id)
    else:
        # Create new session
        session_id = ChatService.create_chat_session(user_id, doc_id)
        chat_session = ChatService.get_chat_session(session_id, user_id)
    
    if not chat_session:
        messages.error(request, 'Error creating chat session.')
        return redirect('library:home')
    
    # Convert session _id to id for template compatibility
    chat_session['id'] = str(chat_session['_id'])
    
    context = {
        'document': document,
        'chat_session': chat_session,
        'session_id': session_id
    }
    
    return render(request, 'library/reader.html', context)


@login_required_mongo
@require_http_methods(["POST"])
@csrf_exempt
def chat_message(request):
    """Handle chat messages and return AI responses."""
    try:
        data = json.loads(request.body)
        user_id = request.user.id
        
        session_id = data.get('session_id')
        message = data.get('message', '').strip()
        
        if not session_id or not message:
            return JsonResponse({'error': 'Missing session_id or message'}, status=400)
        
        # Get chat session
        chat_session = ChatService.get_chat_session(session_id, user_id)
        if not chat_session:
            return JsonResponse({'error': 'Chat session not found'}, status=404)
        
        # Add user message to session
        ChatService.add_message_to_session(
            session_id, user_id, 'user', message
        )
        
        # Get conversation history
        conversation_history = []
        for msg in chat_session.get('messages', [])[-10:]:  # Last 10 messages
            conversation_history.append({
                'role': msg['type'],
                'content': msg['content']
            })
        
        # Perform semantic search
        relevant_paragraphs = SemanticSearchService.search_documents(
            message, user_id, top_k=5
        )
        
        # Generate AI response
        ai_response = AIService.generate_response(
            message, relevant_paragraphs, conversation_history
        )
        
        # Add AI response to session
        ChatService.add_message_to_session(
            session_id, user_id, 'assistant', ai_response, {
                'relevant_paragraphs': len(relevant_paragraphs),
                'sources': [p['document_title'] for p in relevant_paragraphs[:3]]
            }
        )
        
        return JsonResponse({
            'response': ai_response,
            'sources': [p['document_title'] for p in relevant_paragraphs[:3]]
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in chat_message: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def chat_history(request, session_id):
    """Get chat history for a session."""
    user_id = request.user.id
    
    chat_session = ChatService.get_chat_session(session_id, user_id)
    if not chat_session:
        return JsonResponse({'error': 'Chat session not found'}, status=404)
    
    messages_data = []
    for msg in chat_session.get('messages', []):
        messages_data.append({
            'type': msg['type'],
            'content': msg['content'],
            'timestamp': msg['timestamp'].isoformat(),
            'metadata': msg.get('metadata', {})
        })
    
    return JsonResponse({'messages': messages_data})


@login_required_mongo
@require_http_methods(["GET"])
def search_documents(request):
    """Search documents using semantic search."""
    user_id = request.user.id
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    try:
        results = SemanticSearchService.search_documents(query, user_id, top_k=10)
        
        # Format results for frontend
        formatted_results = []
        for result in results:
            formatted_results.append({
                'document_id': result['document_id'],
                'document_title': result['document_title'],
                'paragraph': result['paragraph'],
                'similarity': result['similarity']
            })
        
        return JsonResponse({'results': formatted_results})
        
    except Exception as e:
        logger.error(f"Error in search_documents: {e}")
        return JsonResponse({'error': 'Search failed'}, status=500)


@login_required_mongo
@require_http_methods(["DELETE"])
def delete_document(request, doc_id):
    """Delete a document."""
    user_id = request.user.id
    
    try:
        success = DocumentService.delete_document(doc_id, user_id)
        
        if success:
            # Also delete the file
            document = DocumentService.get_document_by_id(doc_id)
            if document and document.get('file_path'):
                try:
                    file_path = os.path.join(settings.MEDIA_ROOT, document['file_path'])
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file: {e}")
            
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Document not found or access denied'}, status=404)
            
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return JsonResponse({'error': 'Delete failed'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def chat_sessions(request):
    """List user's chat sessions."""
    user_id = request.user.id
    page = int(request.GET.get('page', 1))
    page_size = 10
    
    sessions, total = ChatService.get_user_chat_sessions(user_id, page, page_size)
    
    # Add document titles to sessions and convert _id to id
    for session in sessions:
        session['id'] = str(session['_id'])
        if session.get('document_id'):
            doc = DocumentService.get_document_by_id(str(session['document_id']))
            session['document_title'] = doc.get('title', 'Unknown') if doc else 'Unknown'
    
    context = {
        'sessions': sessions,
        'total_sessions': total,
        'page': page
    }
    
    return render(request, 'library/chat_sessions.html', context)


@login_required_mongo
@require_http_methods(["DELETE"])
def delete_chat_session(request, session_id):
    """Delete a chat session."""
    user_id = request.user.id
    
    try:
        success = ChatService.delete_chat_session(session_id, user_id)
        
        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Session not found or access denied'}, status=404)
            
    except Exception as e:
        logger.error(f"Error deleting chat session: {e}")
        return JsonResponse({'error': 'Delete failed'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def document_summary(request, doc_id):
    """Generate AI summary of a document."""
    user_id = request.user.id
    
    try:
        document = DocumentService.get_document_by_id(doc_id)
        if not document or str(document['user_id']) != user_id:
            return JsonResponse({'error': 'Document not found or access denied'}, status=404)
        
        if not document.get('content'):
            return JsonResponse({'error': 'Document content not available'}, status=400)
        
        summary = AIService.generate_document_summary(document['content'])
        
        return JsonResponse({'summary': summary})
        
    except Exception as e:
        logger.error(f"Error generating document summary: {e}")
        return JsonResponse({'error': 'Failed to generate summary'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def document_qa_pairs(request, doc_id):
    """Generate Q&A pairs from document content."""
    user_id = request.user.id
    num_questions = int(request.GET.get('num', 5))
    
    try:
        document = DocumentService.get_document_by_id(doc_id)
        if not document or str(document['user_id']) != user_id:
            return JsonResponse({'error': 'Document not found or access denied'}, status=404)
        
        if not document.get('content'):
            return JsonResponse({'error': 'Document content not available'}, status=400)
        
        qa_pairs = AIService.generate_qa_pairs(document['content'], num_questions)
        
        return JsonResponse({'qa_pairs': qa_pairs})
        
    except Exception as e:
        logger.error(f"Error generating QA pairs: {e}")
        return JsonResponse({'error': 'Failed to generate QA pairs'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def document_analysis(request, doc_id):
    """Get document structure analysis."""
    user_id = request.user.id
    
    try:
        document = DocumentService.get_document_by_id(doc_id)
        if not document or str(document['user_id']) != user_id:
            return JsonResponse({'error': 'Document not found or access denied'}, status=404)
        
        if not document.get('content'):
            return JsonResponse({'error': 'Document content not available'}, status=400)
        
        analysis = AIService.analyze_document_structure(document['content'])
        
        return JsonResponse({'analysis': analysis})
        
    except Exception as e:
        logger.error(f"Error analyzing document: {e}")
        return JsonResponse({'error': 'Failed to analyze document'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def document_export(request, doc_id):
    """Export document content in various formats."""
    user_id = request.user.id
    format_type = request.GET.get('format', 'txt')
    
    try:
        document = DocumentService.get_document_by_id(doc_id)
        if not document or str(document['user_id']) != user_id:
            return JsonResponse({'error': 'Document not found or access denied'}, status=404)
        
        if not document.get('content'):
            return JsonResponse({'error': 'Document content not available'}, status=400)
        
        content = document['content']
        filename = f"{document.get('title', 'document')}.{format_type}"
        
        if format_type == 'txt':
            response = HttpResponse(content, content_type='text/plain')
        elif format_type == 'md':
            # Convert to markdown format
            md_content = f"# {document.get('title', 'Document')}\n\n{content}"
            response = HttpResponse(md_content, content_type='text/markdown')
        elif format_type == 'json':
            # Export as structured JSON
            json_data = {
                'title': document.get('title', ''),
                'filename': document.get('filename', ''),
                'content': content,
                'metadata': document.get('metadata', {}),
                'created_at': document.get('created_at', '').isoformat() if document.get('created_at') else '',
                'word_count': len(content.split()),
                'paragraph_count': len([p for p in content.split('\n\n') if len(p.strip()) > 50])
            }
            response = JsonResponse(json_data, json_dumps_params={'indent': 2})
        else:
            return JsonResponse({'error': 'Unsupported format'}, status=400)
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        logger.error(f"Error exporting document: {e}")
        return JsonResponse({'error': 'Failed to export document'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def analytics_dashboard(request):
    """Analytics dashboard showing document usage statistics."""
    user_id = request.user.id
    
    try:
        # Get user's documents
        documents, total_docs = DocumentService.get_user_documents(user_id, page=1, page_size=1000)
        
        # Get user's chat sessions
        sessions, total_sessions = ChatService.get_user_chat_sessions(user_id, page=1, page_size=1000)
        
        # Calculate analytics
        processed_docs = len([d for d in documents if d.get('is_processed', False)])
        total_words = sum(len(d.get('content', '').split()) for d in documents if d.get('content'))
        total_chat_messages = sum(len(s.get('history', [])) for s in sessions)
        
        # Most active documents (by chat messages)
        doc_activity = {}
        for session in sessions:
            doc_id = str(session.get('document_id', ''))
            if doc_id:
                if doc_id not in doc_activity:
                    doc_activity[doc_id] = 0
                doc_activity[doc_id] += len(session.get('history', []))
        
        # Get document details for most active
        most_active_docs = []
        for doc_id, message_count in sorted(doc_activity.items(), key=lambda x: x[1], reverse=True)[:5]:
            doc = DocumentService.get_document_by_id(doc_id)
            if doc and str(doc['user_id']) == user_id:
                most_active_docs.append({
                    'title': doc.get('title', 'Unknown'),
                    'message_count': message_count,
                    'created_at': doc.get('created_at', '')
                })
        
        # Recent activity
        recent_sessions = sorted(sessions, key=lambda x: x.get('updated_at', ''), reverse=True)[:5]
        recent_activity = []
        for session in recent_sessions:
            doc = DocumentService.get_document_by_id(str(session.get('document_id', '')))
            if doc and str(doc['user_id']) == user_id:
                recent_activity.append({
                    'document_title': doc.get('title', 'Unknown'),
                    'last_activity': session.get('updated_at', ''),
                    'message_count': len(session.get('history', []))
                })
        
        analytics_data = {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'total_words': total_words,
            'total_chat_sessions': total_sessions,
            'total_chat_messages': total_chat_messages,
            'most_active_documents': most_active_docs,
            'recent_activity': recent_activity,
            'processing_rate': round((processed_docs / max(1, total_docs)) * 100, 1),
            'avg_messages_per_session': round(total_chat_messages / max(1, total_sessions), 1),
            'avg_words_per_document': round(total_words / max(1, total_docs), 0)
        }
        
        return JsonResponse({'analytics': analytics_data})
        
    except Exception as e:
        logger.error(f"Error generating analytics: {e}")
        return JsonResponse({'error': 'Failed to generate analytics'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def collaboration_dashboard(request):
    """Collaboration dashboard for document sharing."""
    user_id = request.user.id
    
    try:
        # Get user's documents
        documents, total_docs = DocumentService.get_user_documents(user_id, page=1, page_size=100)
        
        # For now, return basic collaboration info
        # In a full implementation, you'd have shared documents, permissions, etc.
        collaboration_data = {
            'total_documents': total_docs,
            'shared_documents': 0,  # Placeholder
            'collaborators': 0,     # Placeholder
            'recent_shares': [],    # Placeholder
            'pending_invites': []   # Placeholder
        }
        
        return JsonResponse({'collaboration': collaboration_data})
        
    except Exception as e:
        logger.error(f"Error generating collaboration data: {e}")
        return JsonResponse({'error': 'Failed to generate collaboration data'}, status=500)


@login_required_mongo
@require_http_methods(["GET"])
def quick_actions(request):
    """Quick actions for common tasks."""
    user_id = request.user.id
    
    try:
        # Get user's recent documents
        documents, _ = DocumentService.get_user_documents(user_id, page=1, page_size=5)
        
        # Get recent chat sessions
        sessions, _ = ChatService.get_user_chat_sessions(user_id, page=1, page_size=5)
        
        quick_actions_data = {
            'recent_documents': [
                {
                    'id': str(doc['_id']),
                    'title': doc.get('title', 'Unknown'),
                    'is_processed': doc.get('is_processed', False),
                    'created_at': doc.get('created_at', '').isoformat() if doc.get('created_at') else ''
                }
                for doc in documents
            ],
            'recent_sessions': [
                {
                    'id': str(session['_id']),
                    'document_id': str(session.get('document_id', '')),
                    'message_count': len(session.get('history', [])),
                    'updated_at': session.get('updated_at', '').isoformat() if session.get('updated_at') else ''
                }
                for session in sessions
            ],
            'total_documents': len(documents),
            'total_sessions': len(sessions)
        }
        
        return JsonResponse({'quick_actions': quick_actions_data})
        
    except Exception as e:
        logger.error(f"Error generating quick actions: {e}")
        return JsonResponse({'error': 'Failed to generate quick actions'}, status=500)


# Community Views
@login_required_mongo
def community_home(request):
    """Community home page showing posts and discussions."""
    page = int(request.GET.get('page', 1))
    category = request.GET.get('category', 'all')
    search = request.GET.get('search', '')
    
    posts, total = CommunityService.get_posts(page=page, page_size=10, category=category, search=search)
    categories = CommunityService.get_categories()
    popular_posts = CommunityService.get_popular_posts(limit=5)
    
    # Add user info to posts
    for post in posts:
        post['id'] = str(post['_id'])
        post['likes_count'] = len(post.get('likes', []))
        post['comments_count'] = len(post.get('comments', []))
        post['is_liked'] = request.user.id in [str(like) for like in post.get('likes', [])]
    
    # Add user info to popular posts
    for post in popular_posts:
        post['id'] = str(post['_id'])
        post['likes_count'] = len(post.get('likes', []))
        post['comments_count'] = len(post.get('comments', []))
    
    context = {
        'posts': posts,
        'popular_posts': popular_posts,
        'categories': categories,
        'current_category': category,
        'search_query': search,
        'total_posts': total,
        'page': page
    }
    
    return render(request, 'library/community.html', context)


@login_required_mongo
def create_post(request):
    """Create a new community post."""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category = request.POST.get('category', 'general')
        tags = [tag.strip() for tag in request.POST.get('tags', '').split(',') if tag.strip()]
        
        if not title or not content:
            messages.error(request, 'Le titre et le contenu sont obligatoires.')
            return redirect('library:create_post')
        
        try:
            post_id = CommunityService.create_post(
                user_id=request.user.id,
                title=title,
                content=content,
                category=category,
                tags=tags
            )
            messages.success(request, 'Votre post a été créé avec succès!')
            return redirect('library:view_post', post_id=post_id)
        except Exception as e:
            logger.error(f"Error creating post: {e}")
            messages.error(request, 'Une erreur est survenue lors de la création du post.')
            return redirect('library:create_post')
    
    categories = ['general', 'question', 'help', 'experience', 'tip', 'discussion']
    context = {'categories': categories}
    return render(request, 'library/create_post.html', context)


@login_required_mongo
def view_post(request, post_id):
    """View a specific post with comments."""
    post = CommunityService.get_post_by_id(post_id)
    if not post:
        messages.error(request, 'Post non trouvé.')
        return redirect('library:community')
    
    # Increment view count
    CommunityService.increment_views(post_id)
    
    # Add user info
    post['id'] = str(post['_id'])
    post['likes_count'] = len(post.get('likes', []))
    post['comments_count'] = len(post.get('comments', []))
    post['is_liked'] = request.user.id in [str(like) for like in post.get('likes', [])]
    post['is_author'] = str(post['user_id']) == request.user.id
    
    # Add user info to comments
    for comment in post.get('comments', []):
        comment['id'] = str(comment.get('_id', ''))
        comment['likes_count'] = len(comment.get('likes', []))
        comment['is_liked'] = request.user.id in [str(like) for like in comment.get('likes', [])]
        comment['is_author'] = str(comment['user_id']) == request.user.id
    
    context = {'post': post}
    return render(request, 'library/view_post.html', context)


@login_required_mongo
@require_http_methods(["POST"])
@csrf_exempt
def add_comment(request):
    """Add a comment to a post."""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        content = data.get('content', '').strip()
        
        if not post_id or not content:
            return JsonResponse({'error': 'Post ID et contenu requis'}, status=400)
        
        result = CommunityService.add_comment(post_id, request.user.id, content)
        
        if result == 'success':
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Erreur lors de l\'ajout du commentaire'}, status=500)
            
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return JsonResponse({'error': 'Erreur interne'}, status=500)


@login_required_mongo
@require_http_methods(["POST"])
@csrf_exempt
def toggle_like(request):
    """Toggle like on a post."""
    try:
        data = json.loads(request.body)
        post_id = data.get('post_id')
        
        if not post_id:
            return JsonResponse({'error': 'Post ID requis'}, status=400)
        
        result = CommunityService.toggle_like(post_id, request.user.id)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'liked': result['liked'],
                'count': result['count']
            })
        else:
            return JsonResponse({'error': result.get('error', 'Erreur inconnue')}, status=500)
            
    except Exception as e:
        logger.error(f"Error toggling like: {e}")
        return JsonResponse({'error': 'Erreur interne'}, status=500)


@login_required_mongo
@require_http_methods(["DELETE"])
def delete_post(request, post_id):
    """Delete a post."""
    try:
        success = CommunityService.delete_post(post_id, request.user.id)
        
        if success:
            messages.success(request, 'Post supprimé avec succès.')
            return JsonResponse({'success': True})
        else:
            messages.error(request, 'Post non trouvé ou accès refusé.')
            return JsonResponse({'error': 'Post non trouvé ou accès refusé'}, status=404)
            
    except Exception as e:
        logger.error(f"Error deleting post: {e}")
        return JsonResponse({'error': 'Erreur lors de la suppression'}, status=500)


@login_required_mongo
def my_posts(request):
    """View user's own posts."""
    page = int(request.GET.get('page', 1))
    posts, total = CommunityService.get_user_posts(request.user.id, page=page, page_size=10)
    
    # Add user info
    for post in posts:
        post['id'] = str(post['_id'])
        post['likes_count'] = len(post.get('likes', []))
        post['comments_count'] = len(post.get('comments', []))
    
    context = {
        'posts': posts,
        'total_posts': total,
        'page': page
    }
    
    return render(request, 'library/my_posts.html', context)
