
import re
import os
import json
import random
from collections import Counter
from typing import List, Optional

# Try modern pypdf first, fallback to PyPDF2 adapter
try:
    from pypdf import PdfReader as _PdfReader  # type: ignore
    _PDF_READER_NAME = "pypdf"
except Exception:
    try:
        import PyPDF2

        class _PdfReader:  # adapter
            def __init__(self, fh):
                self._reader = PyPDF2.PdfReader(fh)

            @property
            def pages(self):
                return self._reader.pages

        _PDF_READER_NAME = "PyPDF2"
    except Exception:
        _PdfReader = None
        _PDF_READER_NAME = "none"

try:
    import requests
except Exception:
    requests = None

# Minimal English stopword set to avoid heavy runtime deps (not exhaustive)
EN_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", "further",
    "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "why", "with", "would", "you", "your", "yours", "yourself", "yourselves"
}


def extract_text_from_pdf(path: str) -> str:
    """Extract text from PDF using available reader. Returns empty string on failure."""
    if _PdfReader is None:
        return ""

    parts: List[str] = []
    try:
        with open(path, "rb") as fh:
            reader = _PdfReader(fh)
            for p in getattr(reader, "pages", []):
                try:
                    if hasattr(p, "extract_text"):
                        page_text = p.extract_text() or ""
                    elif hasattr(p, "extractText"):
                        page_text = p.extractText() or ""
                    else:
                        page_text = ""
                except Exception:
                    page_text = ""
                parts.append(page_text)
    except Exception:
        return ""

    return "\n".join(parts)


def simple_sent_tokenize(text: str) -> List[str]:
    """Very small sentence splitter: splits on .!? followed by whitespace. """
    if not text:
        return []
    parts = re.split(r'(?<=[.!?])\s+', text.replace('\r\n', '\n'))
    return [p.strip() for p in parts if p and len(p) > 10]


def top_n_keywords(text: str, n: int = 10) -> List[str]:
    words = re.findall(r"\w+", (text or "").lower())
    filtered = [w for w in words if w not in EN_STOPWORDS and len(w) > 3]
    return [w for w, _ in Counter(filtered).most_common(n)]


def generate_distractors(correct_answer: str, all_words: list, num_distractors: int = 3) -> List[str]:
    """Generate plausible distractors for a correct answer using local words."""
    similar_length = [w for w in all_words if abs(len(w) - len(correct_answer)) <= 3 and w != correct_answer.lower()]
    if len(similar_length) < num_distractors:
        similar_length = [w for w in all_words if w != correct_answer.lower()]
    random.shuffle(similar_length)
    distractors = similar_length[:num_distractors]
    while len(distractors) < num_distractors:
        distractors.append(f"Option {len(distractors) + 1}")
    return distractors[:num_distractors]


def _call_openai_for_questions(text: str, num_questions: int = 5) -> Optional[list]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or requests is None:
        return None
    prompt = (
        f"Create {num_questions} multiple-choice questions from the following text. "
        "Each question should have exactly four options labeled A-D, indicate which option is correct by letter, "
        "and include the short source sentence. Respond in JSON array format where each item is: "
        "{question, options: {A,B,C,D}, correct_answer, answer_text, source}.\n\nText:\n" + text[:6000]
    )
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 1600}
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            return parsed
        except Exception:
            m = re.search(r"(\[\s*\{.*\}\s*\])", content, flags=re.S)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    return None
    except Exception:
        return None


def generate_questions_from_text(pdf_path: str, num_questions: int = 5) -> list:
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        return []
    try:
        oa = _call_openai_for_questions(text, num_questions=num_questions)
        if oa:
            return oa[:num_questions]
    except Exception:
        pass
    sents = simple_sent_tokenize(text)
    keywords = top_n_keywords(text, n=20)
    all_words = re.findall(r"\w+", text.lower())
    all_words = [w for w in all_words if w not in EN_STOPWORDS and len(w) > 3]
    all_words = list(set(all_words))
    questions = []
    for kw in keywords[: num_questions * 2]:
        for s in sents:
            if kw in s.lower() and len(s.split()) > 6:
                masked = re.sub(r"(?i)\b(" + re.escape(kw) + r")\b", "_____", s, count=1)
                distractors = generate_distractors(kw, all_words, num_distractors=3)
                options = [kw] + distractors
                while len(options) < 4:
                    options.append(f"Option {len(options)+1}")
                random.shuffle(options)
                correct_index = options.index(kw) if kw in options else 0
                correct_letter = chr(65 + correct_index)
                questions.append({"question": masked, "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]}, "correct_answer": correct_letter, "answer_text": kw, "source": s})
                break
        if len(questions) >= num_questions:
            break
    if len(questions) < num_questions:
        longs = sorted(sents, key=lambda x: -len(x))[: num_questions * 2]
        for s in longs:
            if len(questions) >= num_questions:
                break
            words = [w for w in re.findall(r"\w+", s) if len(w) > 3]
            if not words:
                continue
            kw = words[len(words) // 3]
            masked = s.replace(kw, "_____", 1)
            distractors = generate_distractors(kw, all_words, num_distractors=3)
            options = [kw] + distractors
            while len(options) < 4:
                options.append(f"Option {len(options)+1}")
            random.shuffle(options)
            correct_index = options.index(kw) if kw in options else 0
            correct_letter = chr(65 + correct_index)
            questions.append({"question": masked, "options": {"A": options[0], "B": options[1], "C": options[2], "D": options[3]}, "correct_answer": correct_letter, "answer_text": kw, "source": s})
    return questions[:num_questions]


def _call_openai_for_summary(text: str, num_sentences: int = 5) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or requests is None:
        return None
    prompt = (f"Please produce a concise extractive-style summary in {num_sentences} sentences of the following text. " "Respond with JSON: {summary: string}.\n\nText:\n" + text[:12000])
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            return parsed.get("summary") if isinstance(parsed, dict) else None
        except Exception:
            return content.strip()
    except Exception:
        return None


def generate_summary_from_text(pdf_path: str, num_sentences: int = 5) -> dict:
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        return {"summary": "Le document est vide ou le texte n'a pas pu être extrait.", "word_count": 0, "sentence_count": 0, "key_topics": []}
    try:
        oa = _call_openai_for_summary(text, num_sentences=num_sentences)
        if oa:
            words = re.findall(r"\w+", text)
            sents = simple_sent_tokenize(text)
            return {"summary": oa, "word_count": len(words), "sentence_count": len(sents), "key_topics": top_n_keywords(text, 5)}
    except Exception:
        pass
    sentences = simple_sent_tokenize(text)
    if not sentences:
        return {"summary": "Aucune phrase détectée dans le document.", "word_count": 0, "sentence_count": 0, "key_topics": []}
    words = re.findall(r"\w+", text.lower())
    filtered_words = [w for w in words if w not in EN_STOPWORDS and len(w) > 3]
    word_freq = Counter(filtered_words)
    top_keywords = [w for w, _ in word_freq.most_common(10)]
    sentence_scores = {}
    for i, sentence in enumerate(sentences):
        score = 0
        words_in_sentence = re.findall(r"\w+", sentence.lower())
        for word in words_in_sentence:
            if word in word_freq:
                score += word_freq[word]
        sentence_scores[i] = score / len(words_in_sentence) if words_in_sentence else 0
    top_sentence_indices = sorted(sentence_scores.items(), key=lambda x: -x[1])[:num_sentences]
    top_sentence_indices = sorted([idx for idx, _ in top_sentence_indices])
    summary_sentences = [sentences[i] for i in top_sentence_indices]
    summary_text = " ".join(summary_sentences)
    total_words = len(words)
    total_sentences = len(sentences)
    return {"summary": summary_text, "word_count": total_words, "sentence_count": total_sentences, "key_topics": top_keywords[:5], "summary_length": len(summary_sentences)}
