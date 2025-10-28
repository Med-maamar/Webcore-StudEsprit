"""
Core services for the Library module including PDF processing, embeddings, and AI responses.
"""

from __future__ import annotations

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# Optional imports - will be handled gracefully if not available
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception as e:
    # Catch broad exceptions to avoid crashes due to binary incompatibilities
    # (e.g., NumPy 2.x with older compiled extensions via torch)
    logging.getLogger(__name__).warning(
        "sentence-transformers unavailable, falling back. Reason: %s", str(e)
    )
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from django.conf import settings
from library.models import DocumentService, EmbeddingService

logger = logging.getLogger(__name__)

# Global model instance for embeddings
_embedding_model = None


def get_embedding_model():
    """Get or create the sentence transformer model."""
    global _embedding_model
    if _embedding_model is None and SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            # Use a lightweight model for better performance
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            # Fallback to a simple model
            try:
                _embedding_model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
            except Exception as e2:
                logger.error(f"Failed to load fallback embedding model: {e2}")
                _embedding_model = None
    return _embedding_model


class PDFProcessor:
    """Service for processing PDF documents."""
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract text from PDF file using PyMuPDF.
        Returns extracted text and metadata.
        """
        if not PYMUPDF_AVAILABLE:
            raise Exception("PyMuPDF is not installed. Please install it with: pip install PyMuPDF")
        
        try:
            doc = fitz.open(file_path)
            text_content = []
            metadata = {
                "page_count": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
                "modification_date": doc.metadata.get("modDate", "")
            }
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                if page_text.strip():
                    text_content.append(f"Page {page_num + 1}:\n{page_text}")
            
            doc.close()
            
            full_text = "\n\n".join(text_content)
            return full_text, metadata
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
    
    @staticmethod
    def split_text_into_paragraphs(text: str, min_length: int = 100, max_length: int = 1000) -> List[str]:
        """
        Split text into meaningful paragraphs for embedding.
        """
        if not text or not text.strip():
            return []
        
        # Clean the text
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Split by double newlines first
        paragraphs = re.split(r'\n\s*\n', text)
        
        processed_paragraphs = []
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if len(paragraph) < min_length:
                continue
            
            # If paragraph is too long, split by sentences
            if len(paragraph) > max_length:
                sentences = re.split(r'[.!?]+', paragraph)
                current_chunk = ""
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    if len(current_chunk + sentence) > max_length and current_chunk:
                        processed_paragraphs.append(current_chunk.strip())
                        current_chunk = sentence
                    else:
                        current_chunk += " " + sentence if current_chunk else sentence
                
                if current_chunk.strip():
                    processed_paragraphs.append(current_chunk.strip())
            else:
                processed_paragraphs.append(paragraph)
        
        return processed_paragraphs


class EmbeddingProcessor:
    """Service for generating and managing embeddings."""
    
    @staticmethod
    def generate_embeddings(texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using sentence transformers.
        """
        if not texts:
            return []
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers not available, using fallback embeddings")
            return [EmbeddingProcessor._fallback_embedding(text) for text in texts]
        
        try:
            model = get_embedding_model()
            if model is None:
                return [EmbeddingProcessor._fallback_embedding(text) for text in texts]
            
            embeddings = model.encode(texts, convert_to_tensor=False)
            
            # Convert numpy arrays to lists
            return [embedding.tolist() for embedding in embeddings]
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Fallback to simple hash-based embeddings
            return [EmbeddingProcessor._fallback_embedding(text) for text in texts]
    
    @staticmethod
    def _fallback_embedding(text: str) -> List[float]:
        """Fallback embedding using simple hash-based approach."""
        import hashlib
        import math
        
        # Use the existing embedding function from ai.embeddings
        from ai.embeddings import compute_embedding
        return compute_embedding(text)
    
    @staticmethod
    def process_document_embeddings(doc_id: str) -> bool:
        """
        Process a document to generate embeddings for all paragraphs.
        """
        try:
            doc = DocumentService.get_document_by_id(doc_id)
            if not doc or not doc.get("content"):
                return False
            
            # Split content into paragraphs
            paragraphs = PDFProcessor.split_text_into_paragraphs(doc["content"])
            
            if not paragraphs:
                return False
            
            # Generate embeddings
            embeddings = EmbeddingProcessor.generate_embeddings(paragraphs)
            
            # Update document with processed data
            DocumentService.update_document_processing(doc_id, paragraphs, embeddings)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing document embeddings for {doc_id}: {e}")
            return False


class AIService:
    """Service for AI-powered responses using OpenAI or fallback."""
    
    @staticmethod
    def generate_response(
        user_question: str,
        relevant_paragraphs: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Generate AI response based on user question and relevant document content.
        """
        try:
            # Try OpenAI first if API key is available
            if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
                return AIService._generate_openai_response(
                    user_question, relevant_paragraphs, conversation_history
                )
            else:
                # Fallback to simple response generation
                return AIService._generate_fallback_response(
                    user_question, relevant_paragraphs
                )
                
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return AIService._generate_fallback_response(user_question, relevant_paragraphs)
    
    @staticmethod
    def generate_document_summary(content: str, max_length: int = 500) -> str:
        """
        Generate a concise summary of the document content.
        """
        try:
            if not OPENAI_AVAILABLE or not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
                return AIService._generate_fallback_summary(content, max_length)
            
            openai.api_key = settings.OPENAI_API_KEY
            
            # Truncate content if too long
            if len(content) > 4000:
                content = content[:4000] + "..."
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": f"Generate a concise summary of the following document content in {max_length} characters or less. Focus on key points, main topics, and important information."
                    },
                    {
                        "role": "user",
                        "content": f"Document content:\n{content}"
                    }
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating document summary: {e}")
            return AIService._generate_fallback_summary(content, max_length)
    
    @staticmethod
    def generate_qa_pairs(content: str, num_questions: int = 5) -> List[Dict[str, str]]:
        """
        Generate question-answer pairs from document content.
        """
        try:
            if not OPENAI_AVAILABLE or not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
                return AIService._generate_fallback_qa_pairs(content, num_questions)
            
            openai.api_key = settings.OPENAI_API_KEY
            
            # Truncate content if too long
            if len(content) > 3000:
                content = content[:3000] + "..."
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": f"Generate {num_questions} question-answer pairs based on the document content. Return them in JSON format: [{{\"question\": \"...\", \"answer\": \"...\"}}]"
                    },
                    {
                        "role": "user",
                        "content": f"Document content:\n{content}"
                    }
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            import json
            qa_pairs = json.loads(response.choices[0].message.content.strip())
            return qa_pairs[:num_questions]
            
        except Exception as e:
            logger.error(f"Error generating QA pairs: {e}")
            return AIService._generate_fallback_qa_pairs(content, num_questions)
    
    @staticmethod
    def analyze_document_structure(content: str) -> Dict[str, Any]:
        """
        Analyze document structure and extract key information.
        """
        try:
            # Extract basic structure information
            paragraphs = content.split('\n\n')
            sentences = content.split('. ')
            
            # Count different types of content
            word_count = len(content.split())
            paragraph_count = len([p for p in paragraphs if len(p.strip()) > 50])
            sentence_count = len([s for s in sentences if len(s.strip()) > 10])
            
            # Extract potential headings (lines that are short and end with colon or are all caps)
            potential_headings = []
            for line in content.split('\n'):
                line = line.strip()
                if (len(line) < 100 and 
                    (line.endswith(':') or line.isupper() or 
                     (len(line.split()) <= 8 and line[0].isupper()))):
                    potential_headings.append(line)
            
            # Extract key topics (simple keyword extraction)
            words = content.lower().split()
            word_freq = {}
            for word in words:
                if len(word) > 4 and word.isalpha():
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top 10 most frequent words
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "word_count": word_count,
                "paragraph_count": paragraph_count,
                "sentence_count": sentence_count,
                "potential_headings": potential_headings[:10],
                "top_keywords": [word for word, freq in top_words],
                "reading_time_minutes": max(1, word_count // 200),  # Average reading speed
                "complexity_score": min(100, (sentence_count / max(1, paragraph_count)) * 10)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing document structure: {e}")
            return {
                "word_count": len(content.split()),
                "paragraph_count": 0,
                "sentence_count": 0,
                "potential_headings": [],
                "top_keywords": [],
                "reading_time_minutes": 1,
                "complexity_score": 50
            }
    
    @staticmethod
    def _generate_fallback_summary(content: str, max_length: int) -> str:
        """Generate a simple fallback summary."""
        sentences = content.split('. ')
        if len(sentences) <= 3:
            return content[:max_length] + "..." if len(content) > max_length else content
        
        # Take first few sentences
        summary = '. '.join(sentences[:3]) + '.'
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        return summary
    
    @staticmethod
    def _generate_fallback_qa_pairs(content: str, num_questions: int) -> List[Dict[str, str]]:
        """Generate simple fallback QA pairs."""
        sentences = [s.strip() for s in content.split('.') if len(s.strip()) > 20]
        qa_pairs = []
        
        for i, sentence in enumerate(sentences[:num_questions]):
            # Simple question generation
            words = sentence.split()
            if len(words) > 5:
                question = f"What is mentioned about {' '.join(words[:3])}?"
                qa_pairs.append({
                    "question": question,
                    "answer": sentence
                })
        
        return qa_pairs
    
    @staticmethod
    def _generate_openai_response(
        user_question: str,
        relevant_paragraphs: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]] = None
    ) -> str:
        """Generate response using OpenAI API."""
        if not OPENAI_AVAILABLE:
            raise Exception("OpenAI library is not installed. Please install it with: pip install openai")
        
        try:
            openai.api_key = settings.OPENAI_API_KEY
            
            # Prepare context from relevant paragraphs
            context_parts = []
            for para in relevant_paragraphs[:3]:  # Use top 3 most relevant
                context_parts.append(f"From '{para['document_title']}': {para['paragraph']}")
            
            context = "\n\n".join(context_parts)
            
            # Prepare conversation history
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful AI reading assistant. Answer questions based on the provided document content. Be concise, accurate, and helpful. If the information isn't available in the provided context, say so clearly."
                }
            ]
            
            # Add conversation history if available
            if conversation_history:
                for msg in conversation_history[-6:]:  # Last 6 messages for context
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Add current question with context
            messages.append({
                "role": "user",
                "content": f"Context from documents:\n{context}\n\nQuestion: {user_question}"
            })
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise e
    
    @staticmethod
    def _generate_fallback_response(
        user_question: str,
        relevant_paragraphs: List[Dict[str, Any]]
    ) -> str:
        """Generate a simple fallback response without external API."""
        if not relevant_paragraphs:
            return "I couldn't find relevant information in your uploaded documents to answer this question. Please make sure you have uploaded relevant documents and try asking a different question."
        
        # Simple keyword matching and response generation
        question_lower = user_question.lower()
        
        # Find the most relevant paragraph
        best_paragraph = relevant_paragraphs[0]
        content = best_paragraph['paragraph']
        doc_title = best_paragraph['document_title']
        
        # Simple response template
        response = f"Based on the document '{doc_title}', here's what I found:\n\n{content[:300]}..."
        
        if len(content) > 300:
            response += "\n\nThis is an excerpt from the document. Would you like me to provide more details about this topic?"
        
        return response


class SemanticSearchService:
    """Service for semantic search across user documents."""
    
    @staticmethod
    def search_documents(
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search across user's documents.
        """
        try:
            # Get user's documents
            user_docs, _ = DocumentService.get_user_documents(user_id, page=1, page_size=100)
            doc_ids = [str(doc["_id"]) for doc in user_docs if doc.get("is_processed")]
            
            if not doc_ids:
                return []
            
            # Generate query embedding
            query_embedding = EmbeddingProcessor.generate_embeddings([query])[0]
            
            # Search for similar paragraphs
            similar_paragraphs = EmbeddingService.search_similar_paragraphs(
                query_embedding, doc_ids, top_k
            )
            
            return similar_paragraphs
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []


def process_uploaded_document(file_path: str, doc_id: str) -> bool:
    """
    Process an uploaded PDF document: extract text, generate embeddings.
    This function is designed to be called asynchronously.
    """
    try:
        # Extract text from PDF
        text_content, metadata = PDFProcessor.extract_text_from_pdf(file_path)
        
        # Update document with extracted content
        from core.mongo import get_db
        from bson import ObjectId
        
        db = get_db()
        db.documents.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {
                    "content": text_content,
                    "metadata": metadata,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Process embeddings
        success = EmbeddingProcessor.process_document_embeddings(doc_id)
        
        return success
        
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {e}")
        return False
