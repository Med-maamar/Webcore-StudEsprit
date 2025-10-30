import PyPDF2
import re
import nltk
import random
from nltk.tokenize import sent_tokenize, word_tokenize
from collections import Counter


def _ensure_nltk_data():
    """Ensure NLTK data is available across versions.

    NLTK >=3.9 split punkt into a new resource 'punkt_tab'. Try both to be
    compatible on any environment.
    """
    # punkt / punkt_tab
    try:
        nltk.data.find('tokenizers/punkt')
    except Exception:
        try:
            nltk.download('punkt')
        except Exception:
            pass
    # Some newer versions expect punkt_tab
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except Exception:
        try:
            nltk.download('punkt_tab')
        except Exception:
            pass
    # stopwords
    try:
        nltk.data.find('corpora/stopwords')
    except Exception:
        try:
            nltk.download('stopwords')
        except Exception:
            pass


def extract_text_from_pdf(path: str) -> str:
    text = []
    with open(path, 'rb') as fh:
        reader = PyPDF2.PdfReader(fh)
        for p in reader.pages:
            try:
                page_text = p.extract_text() or ''
            except Exception:
                page_text = ''
            text.append(page_text)
    return '\n'.join(text)


def top_n_keywords(text: str, n=10):
    words = re.findall(r"\w+", text.lower())
    stopwords = set(nltk.corpus.stopwords.words('english')) if 'english' in nltk.corpus.stopwords.fileids() else set()
    filtered = [w for w in words if w not in stopwords and len(w) > 2]
    return [w for w, _ in Counter(filtered).most_common(n)]


def generate_distractors(correct_answer: str, all_words: list, num_distractors=3):
    """Generate plausible distractor answers for a quiz question."""
    # Filter words of similar length to the correct answer
    similar_length = [w for w in all_words if abs(len(w) - len(correct_answer)) <= 3 and w != correct_answer.lower()]
    
    # If we don't have enough similar words, use any words
    if len(similar_length) < num_distractors:
        similar_length = [w for w in all_words if w != correct_answer.lower()]
    
    # Shuffle and take the required number
    random.shuffle(similar_length)
    distractors = similar_length[:num_distractors]
    
    # If still not enough, generate generic distractors
    while len(distractors) < num_distractors:
        distractors.append(f"Option {len(distractors) + 1}")
    
    return distractors[:num_distractors]


def generate_questions_from_text(pdf_path: str, num_questions=5):
    try:
        # ensure nltk data across versions
        _ensure_nltk_data()

        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            return []
        
        sents = sent_tokenize(text)
        keywords = top_n_keywords(text, n=20)
        
        # Get all words for generating distractors
        all_words = re.findall(r"\w+", text.lower())
        stopwords = set(nltk.corpus.stopwords.words('english')) if 'english' in nltk.corpus.stopwords.fileids() else set()
        all_words = [w for w in all_words if w not in stopwords and len(w) > 3]
        all_words = list(set(all_words))  # Remove duplicates
        
        questions = []
        
        # Choose sentences that contain keywords for quiz questions
        for kw in keywords[:num_questions * 2]:  # Process more to ensure we get enough good questions
            for s in sents:
                if kw in s.lower() and len(s.split()) > 6:
                    # Create a multiple-choice question by masking the keyword
                    masked = re.sub(r'(?i)\b(' + re.escape(kw) + r')\b', '_____', s, count=1)
                    
                    # Generate distractors (wrong answers)
                    distractors = generate_distractors(kw, all_words, num_distractors=3)
                    
                    # Create options list with correct answer and distractors
                    options = [kw] + distractors
                    random.shuffle(options)  # Randomize option order
                    
                    # Find the index of the correct answer (A, B, C, or D)
                    correct_index = options.index(kw)
                    correct_letter = chr(65 + correct_index)  # A=65 in ASCII
                    
                    questions.append({
                        'question': masked,
                        'options': {
                            'A': options[0],
                            'B': options[1],
                            'C': options[2],
                            'D': options[3]
                        },
                        'correct_answer': correct_letter,
                        'answer_text': kw,
                        'source': s
                    })
                    break
            
            if len(questions) >= num_questions:
                break
        
        # Fallback: if not enough questions, take longest sentences
        if len(questions) < num_questions:
            longs = sorted(sents, key=lambda x: -len(x))[:num_questions * 2]
            for s in longs:
                if len(questions) >= num_questions:
                    break
                    
                words = [w for w in re.findall(r"\w+", s) if len(w) > 3]
                if not words:
                    continue
                
                kw = words[len(words) // 3]  # Take a word from the middle
                masked = s.replace(kw, '_____', 1)
                
                # Generate distractors
                distractors = generate_distractors(kw, all_words, num_distractors=3)
                
                # Create options
                options = [kw] + distractors
                random.shuffle(options)
                
                correct_index = options.index(kw)
                correct_letter = chr(65 + correct_index)
                
                questions.append({
                    'question': masked,
                    'options': {
                        'A': options[0],
                        'B': options[1],
                        'C': options[2],
                        'D': options[3]
                    },
                    'correct_answer': correct_letter,
                    'answer_text': kw,
                    'source': s
                })
        
        return questions[:num_questions]  # Return exactly num_questions
    except Exception as e:
        raise


def generate_summary_from_text(pdf_path: str, num_sentences=5):
    """
    Generate a summary of the PDF content using extractive summarization.
    Selects the most important sentences based on keyword frequency.
    """
    try:
        # Ensure nltk data across versions
        _ensure_nltk_data()
        
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            return {
                'summary': 'Le document est vide ou le texte n\'a pas pu être extrait.',
                'word_count': 0,
                'sentence_count': 0,
                'key_topics': []
            }
        
        # Tokenize into sentences
        sentences = sent_tokenize(text)
        if len(sentences) == 0:
            return {
                'summary': 'Aucune phrase détectée dans le document.',
                'word_count': 0,
                'sentence_count': 0,
                'key_topics': []
            }
        
        # Get word frequency
        words = re.findall(r"\w+", text.lower())
        stopwords = set(nltk.corpus.stopwords.words('english')) if 'english' in nltk.corpus.stopwords.fileids() else set()
        filtered_words = [w for w in words if w not in stopwords and len(w) > 3]
        word_freq = Counter(filtered_words)
        
        # Get top keywords
        top_keywords = [w for w, _ in word_freq.most_common(10)]
        
        # Score sentences based on keyword frequency
        sentence_scores = {}
        for i, sentence in enumerate(sentences):
            score = 0
            words_in_sentence = re.findall(r"\w+", sentence.lower())
            for word in words_in_sentence:
                if word in word_freq:
                    score += word_freq[word]
            # Normalize by sentence length to avoid bias toward long sentences
            if len(words_in_sentence) > 0:
                sentence_scores[i] = score / len(words_in_sentence)
            else:
                sentence_scores[i] = 0
        
        # Select top N sentences
        top_sentence_indices = sorted(sentence_scores.items(), key=lambda x: -x[1])[:num_sentences]
        # Sort by original order to maintain coherence
        top_sentence_indices = sorted([idx for idx, score in top_sentence_indices])
        
        # Build summary
        summary_sentences = [sentences[i] for i in top_sentence_indices]
        summary_text = ' '.join(summary_sentences)
        
        # Count statistics
        total_words = len(words)
        total_sentences = len(sentences)
        
        return {
            'summary': summary_text,
            'word_count': total_words,
            'sentence_count': total_sentences,
            'key_topics': top_keywords[:5],  # Top 5 keywords
            'summary_length': len(summary_sentences)
        }
    
    except Exception as e:
        return {
            'summary': f'Erreur lors de la génération du résumé: {str(e)}',
            'word_count': 0,
            'sentence_count': 0,
            'key_topics': [],
            'error': str(e)
        }
