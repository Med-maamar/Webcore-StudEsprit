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

import json
import math

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
        # New structured summary for students. Limit by approximate reading time (minutes)
        reading_minutes = 5
        try:
            # Determine approximate max words for requested reading time
            max_words = reading_minutes * 200  # ~200 wpm

            if not OPENAI_AVAILABLE or not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
                # Fallback: create a structured summary using simple heuristics
                return AIService._generate_structured_fallback_summary(content, reading_minutes)

            openai.api_key = settings.OPENAI_API_KEY

            # Truncate content to a reasonable context window for the model
            if len(content) > 12000:
                content = content[:12000] + "..."

            prompt_system = (
                "You are an expert assistant that creates concise, professional study summaries for university students. "
                "Produce a structured summary with these sections: Title (very short), Key Concepts (3-6 bullet points), "
                "Definitions (3-6 short definitions), Examples (2-4 short examples), Study Tips (4-6 actionable tips), and a short Summary paragraph. "
                "Keep the whole output suitable to be read in approximately 5 minutes (~200-1000 words). Be precise and do not hallucinate facts not in the source."
            )

            prompt_user = (
                "Document content:\n" + content +
                "\n\nReturn the result in JSON with keys: title, key_concepts (list), definitions (list of objects with keys term and definition), examples (list), study_tips (list), summary (string)."
            )

            # Allow enough tokens for the structured output
            max_tokens = min(1500, max_words * 2)

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": prompt_user}
                ],
                max_tokens=max_tokens,
                temperature=0.3
            )

            raw = response.choices[0].message.content.strip()

            # Try to parse JSON from the model. If it fails, treat raw text as plain summary.
            try:
                parsed = json.loads(raw)
                # Build a friendly text output for backwards compatibility
                out_lines = []
                if parsed.get('title'):
                    out_lines.append(parsed['title'])
                    out_lines.append('')

                if parsed.get('key_concepts'):
                    out_lines.append('Key Concepts:')
                    for kc in parsed['key_concepts']:
                        out_lines.append(f"- {kc}")
                    out_lines.append('')

                if parsed.get('definitions'):
                    out_lines.append('Definitions:')
                    for d in parsed['definitions']:
                        term = d.get('term') if isinstance(d, dict) else (d[0] if isinstance(d, (list,tuple)) and len(d)>0 else '')
                        definition = d.get('definition') if isinstance(d, dict) else (d[1] if isinstance(d, (list,tuple)) and len(d)>1 else str(d))
                        out_lines.append(f"- {term}: {definition}")
                    out_lines.append('')

                if parsed.get('examples'):
                    out_lines.append('Examples:')
                    for ex in parsed['examples']:
                        out_lines.append(f"- {ex}")
                    out_lines.append('')

                if parsed.get('study_tips'):
                    out_lines.append('Study Tips:')
                    for tip in parsed['study_tips']:
                        out_lines.append(f"- {tip}")
                    out_lines.append('')

                if parsed.get('summary'):
                    out_lines.append('Summary:')
                    out_lines.append(parsed['summary'])

                return '\n'.join(out_lines)
            except Exception:
                # If JSON parse fails, return raw text but keep it concise
                return raw

        except Exception as e:
            logger.error(f"Error generating document summary: {e}")
            return AIService._generate_structured_fallback_summary(content, reading_minutes)
    
    @staticmethod
    def generate_qa_pairs(content: str, num_questions: int = 5) -> List[Dict[str, str]]:
        """
        Generate question-answer pairs from document content.
        """
        try:
            # Split into paragraphs and compute embeddings to find important paragraphs
            paragraphs = PDFProcessor.split_text_into_paragraphs(content, min_length=80, max_length=1200)

            if not paragraphs:
                return AIService._generate_fallback_qa_pairs(content, num_questions)

            # Generate embeddings for paragraphs (may fallback)
            para_embeddings = EmbeddingProcessor.generate_embeddings(paragraphs)

            # Compute centrality score using cosine similarity to other paragraphs
            scores = [0.0] * len(para_embeddings)
            try:
                if SKLEARN_AVAILABLE:
                    # sklearn's cosine_similarity expects 2D arrays
                    sims = cosine_similarity(para_embeddings)
                    for i in range(len(sims)):
                        scores[i] = float(sims[i].sum())
                elif NUMPY_AVAILABLE:
                    import numpy as _np
                    embs = _np.array(para_embeddings)
                    norms = _np.linalg.norm(embs, axis=1, keepdims=True)
                    norms[norms==0] = 1.0
                    embs_norm = embs / norms
                    sims = embs_norm.dot(embs_norm.T)
                    for i in range(sims.shape[0]):
                        scores[i] = float(sims[i].sum())
                else:
                    # No efficient similarity lib — fallback to paragraph length heuristic
                    for i, p in enumerate(paragraphs):
                        scores[i] = len(p)
            except Exception as e:
                logger.warning(f"Embedding similarity failed, falling back to length heuristic: {e}")
                for i, p in enumerate(paragraphs):
                    scores[i] = len(p)

            # Select top paragraphs by score (avoid duplicates)
            idxs = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            selected_idxs = idxs[:min(len(idxs), num_questions * 2)]  # take extra to allow diverse q types

            # Prepare a compact context made of selected paragraphs
            context_parts = []
            references = {}
            for rank, i in enumerate(selected_idxs):
                snippet = paragraphs[i]
                context_parts.append(f"Paragraph {i+1}: {snippet}")
                references[i] = snippet

            compact_context = "\n\n".join(context_parts)

            if not OPENAI_AVAILABLE or not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
                # Fallback structured generation using paragraphs
                return AIService._generate_structured_fallback_qa(paragraphs, num_questions)

            openai.api_key = settings.OPENAI_API_KEY

            # Ask the model to generate a mixture of MCQ, TF, short answer with difficulty and references
            system_prompt = (
                "You are an educational content creator. From the provided document paragraphs, generate exam-style questions. "
                "Only produce multiple-choice (mcq) and true/false (tf) questions. Do NOT produce short-answer questions. "
                "For each question include: type (mcq/tf), difficulty (easy/medium/hard), question, options (for mcq), answer, and reference (paragraph number). "
                "Ensure questions are directly supported by the referenced paragraph and are professional and clear. Return valid JSON list."
            )

            user_prompt = f"Document excerpts:\n{compact_context}\n\nGenerate {num_questions} questions as described. Return JSON array of objects with keys: type,difficulty,question,options,answer,reference."

            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1200,
                temperature=0.2
            )

            raw = resp.choices[0].message.content.strip()
            try:
                generated = json.loads(raw)
                # Normalize and ensure fields
                out = []
                for q in generated[:num_questions]:
                    qtype = q.get('type', 'tf')
                    difficulty = q.get('difficulty', 'medium')
                    question_text = q.get('question', '').strip()
                    options = q.get('options') if isinstance(q.get('options'), list) else []
                    answer = q.get('answer', '')
                    reference = q.get('reference', '')
                    if qtype not in ['mcq', 'tf']:
                        qtype = 'tf'
                        options = []
                    out.append({
                        'type': qtype,
                        'difficulty': difficulty,
                        'question': question_text,
                        'options': options,
                        'answer': answer,
                        'reference': reference
                    })
                return out
            except Exception:
                logger.error('Failed to parse QA JSON from model, falling back to simple QA')
                return AIService._generate_structured_fallback_qa(paragraphs, num_questions)

        except Exception as e:
            logger.error(f"Error generating QA pairs: {e}")
            return AIService._generate_structured_fallback_qa(PDFProcessor.split_text_into_paragraphs(content), num_questions)
    
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
            words = [w for w in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", content.lower())]
            word_freq = {}
            for word in words:
                if len(word) > 4:
                    word_freq[word] = word_freq.get(word, 0) + 1

            # Get top 10 most frequent words
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]

            # Additional readability and richness metrics
            unique_words = set(words)
            unique_ratio = round((len(unique_words) / max(1, len(words))) * 100, 1)
            avg_sentence_len = round((len(content.split()) / max(1, sentence_count)), 1)

            # Approximate Flesch-Kincaid Grade Level (very rough, language-agnostic heuristic)
            syllables = sum(len(re.findall(r"[aeiouyàâäéèêëîïôöùûüÿAEIOUY]", w)) for w in words)
            words_count = max(1, len(words))
            fk_grade = round(0.39 * (words_count / max(1, sentence_count)) + 11.8 * (syllables / words_count) - 15.59, 1)

            # Heuristics: counts of figures/tables/references
            figures = len(re.findall(r"figure\s+\d+|fig\.\s*\d+", content, flags=re.IGNORECASE))
            tables = len(re.findall(r"table\s+\d+", content, flags=re.IGNORECASE))
            references = len(re.findall(r"\[(?:\d+|[A-Za-z]+\s\d{4})\]", content))

            return {
                "word_count": word_count,
                "paragraph_count": paragraph_count,
                "sentence_count": sentence_count,
                "potential_headings": potential_headings[:10],
                "top_keywords": [word for word, freq in top_words],
                "reading_time_minutes": max(1, word_count // 200),  # Average reading speed
                "complexity_score": min(100, (sentence_count / max(1, paragraph_count)) * 10),
                # Enriched metrics
                "unique_word_ratio_percent": unique_ratio,
                "avg_sentence_length": avg_sentence_len,
                "readability_grade_fk": fk_grade,
                "figures_count": figures,
                "tables_count": tables,
                "references_markers": references
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
    def _generate_structured_fallback_summary(content: str, reading_minutes: int = 5) -> str:
        """Create a simple structured summary when no AI model is available.

        Sections: Title, Key Concepts, Definitions, Examples, Study Tips, Summary
        """
        try:
            max_words = reading_minutes * 200
            # Simple sentence splitting
            sentences = [s.strip() for s in re.split(r'[\n\.\?\!]+', content) if s.strip()]
            title = sentences[0] if sentences else 'Résumé du document'

            # Keyword extraction (naive)
            words = re.findall(r"\b[a-zA-Z]{5,}\b", content.lower())
            freq = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            top_words = [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:6]]

            key_concepts = top_words[:6]

            # Definitions: pick sentences that contain top words
            definitions = []
            for w in key_concepts:
                found = next((s for s in sentences if w in s.lower()), '')
                definitions.append({'term': w, 'definition': (found[:180] + '...') if found else 'Definition not available in text.'})

            # Examples: look for sentences with the word "example" or take two short sentences
            examples = [s for s in sentences if 'example' in s.lower()][:2]
            if len(examples) < 2:
                examples += sentences[1:3]

            # Study tips: generic actionable tips
            study_tips = [
                'Read the Key Concepts and try to explain them in your own words.',
                'Make flashcards for the Definitions and important terms.',
                'Solve practice problems related to the Examples.',
                'Review the Summary and test yourself after 24 hours.'
            ]

            # Compact summary: join first few sentences up to max_words
            summary_sentences = sentences[:6]
            summary = '. '.join(summary_sentences).strip()

            out_lines = []
            out_lines.append(title)
            out_lines.append('')
            out_lines.append('Key Concepts:')
            for kc in key_concepts:
                out_lines.append(f"- {kc}")
            out_lines.append('')
            out_lines.append('Definitions:')
            for d in definitions:
                out_lines.append(f"- {d['term']}: {d['definition']}")
            out_lines.append('')
            out_lines.append('Examples:')
            for ex in examples:
                out_lines.append(f"- {ex}")
            out_lines.append('')
            out_lines.append('Study Tips:')
            for tip in study_tips:
                out_lines.append(f"- {tip}")
            out_lines.append('')
            out_lines.append('Summary:')
            out_lines.append(summary)

            return '\n'.join(out_lines)
        except Exception as e:
            logger.error(f"Fallback structured summary failed: {e}")
            return AIService._generate_fallback_summary(content, 500)

    @staticmethod
    def _generate_structured_fallback_qa(paragraphs: List[str], num_questions: int = 5) -> List[Dict[str, Any]]:
        """Generate basic structured QA (mcq/tf only) using paragraphs when no AI is available."""
        out = []
        try:
            # Alternate mcq and tf
            types = ['mcq', 'tf']
            p_count = len(paragraphs)
            for i in range(min(num_questions, p_count)):
                para = paragraphs[i]
                qtype = types[i % len(types)]
                difficulty = 'easy' if i < num_questions/3 else ('medium' if i < 2*num_questions/3 else 'hard')
                reference = f'Paragraph {i+1}'

                if qtype == 'mcq':
                    # Create a question from the first sentence
                    first_sent = para.split('.')[0][:200]
                    question = f"Which of the following is true based on: {first_sent}?"
                    # naive options: correct is first sentence summary, others are shuffled snippets
                    opts = [first_sent]
                    # create distractors from other paragraphs if available
                    j = i+1
                    while len(opts) < 4 and j < p_count:
                        opts.append(paragraphs[j].split('.')[0][:200])
                        j += 1
                    # pad if needed
                    while len(opts) < 4:
                        opts.append('None of the above')
                    answer = opts[0]
                    out.append({'type': 'mcq', 'difficulty': difficulty, 'question': question, 'options': opts, 'answer': answer, 'reference': reference})

                else:  # tf
                    sent = para.split('.')[0][:200]
                    # create a true statement
                    question = f"True or False: {sent}."
                    answer = 'True'
                    out.append({'type': 'tf', 'difficulty': difficulty, 'question': question, 'options': [], 'answer': answer, 'reference': reference})

            return out[:num_questions]
        except Exception as e:
            logger.error(f"Fallback structured QA failed: {e}")
            return []
    
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
