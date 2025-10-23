"""
URL patterns for the Library module.
"""

from django.urls import path
from . import views

app_name = 'library'

urlpatterns = [
    # Test endpoint (no authentication required)
    path('test/', views.library_test, name='test'),
    # Main library pages
    path('', views.library_home, name='home'),
    path('upload/', views.upload_document, name='upload'),
    path('reader/<str:doc_id>/', views.document_reader, name='reader'),
    path('sessions/', views.chat_sessions, name='chat_sessions'),
    
    # API endpoints
    path('api/chat/', views.chat_message, name='chat_message'),
    path('api/chat/<str:session_id>/history/', views.chat_history, name='chat_history'),
    path('api/search/', views.search_documents, name='search_documents'),
    path('api/documents/<str:doc_id>/delete/', views.delete_document, name='delete_document'),
    path('api/sessions/<str:session_id>/delete/', views.delete_chat_session, name='delete_chat_session'),
    
    # Advanced AI features
    path('api/documents/<str:doc_id>/summary/', views.document_summary, name='document_summary'),
    path('api/documents/<str:doc_id>/qa-pairs/', views.document_qa_pairs, name='document_qa_pairs'),
    path('api/documents/<str:doc_id>/analysis/', views.document_analysis, name='document_analysis'),
    path('api/documents/<str:doc_id>/export/', views.document_export, name='document_export'),
    
    # Dashboard features
    path('api/analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('api/collaboration/', views.collaboration_dashboard, name='collaboration_dashboard'),
    path('api/quick-actions/', views.quick_actions, name='quick_actions'),
    
    # Community features
    path('community/', views.community_home, name='community'),
    path('community/create/', views.create_post, name='create_post'),
    path('community/post/<str:post_id>/', views.view_post, name='view_post'),
    path('community/my-posts/', views.my_posts, name='my_posts'),
    path('api/community/comment/', views.add_comment, name='add_comment'),
    path('api/community/like/', views.toggle_like, name='toggle_like'),
    path('api/community/post/<str:post_id>/delete/', views.delete_post, name='delete_post'),
]
