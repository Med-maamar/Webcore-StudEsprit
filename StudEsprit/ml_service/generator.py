# StudEsprit/generator.py
import fitz  # PyMuPDF
import openai
import os
import re
import random

# Clé OpenAI depuis Render
openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_text(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        return f"Erreur lecture PDF: {e}"

def generate_questions(pdf_path: str, num_questions: int = 5):
    text = extract_text(pdf_path)
    if not text.strip():
        return []

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Tu es un générateur de QCM. Crée des questions à choix multiples (4 options, 1 bonne). Format JSON strict."},
                {"role": "user", "content": f"""
Texte: {text[:4000]}

Crée {num_questions} questions QCM.
Format exact:
[
  {{"question": "Texte ?", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_answer": "A", "answer_text": "..."}},
  ...
]
                """}
            ],
            response_format={ "type": "json_object" },
            max_tokens=800
        )

        import json
        data = json.loads(response.choices[0].message.content)
        questions = data.get('questions', [])

        # Nettoyage final
        for q in questions:
            q['options'] = {k: v.strip() for k, v in q['options'].items()}
            q['question'] = q['question'].strip()
            q['answer_text'] = q['answer_text'].strip()

        return questions[:num_questions]

    except Exception as e:
        return [{"question": "Erreur IA", "options": {"A": str(e)}, "correct_answer": "A", "answer_text": "Voir erreur"}]

def generate_summary(pdf_path: str, num_sentences: int = 5):
    text = extract_text(pdf_path)
    if not text.strip():
        return {"summary": "Document vide.", "key_topics": []}

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Résume en {num_sentences} phrases clés. Retourne JSON."},
                {"role": "user", "content": f"Résume en {num_sentences} phrases:\n\n{text[:5000]}"}
            ],
            response_format={ "type": "json_object" },
            max_tokens=300
        )

        import json
        data = json.loads(response.choices[0].message.content)
        summary = data.get('summary', 'Aucun résumé.')
        topics = data.get('key_topics', [])

        return {
            "summary": summary,
            "key_topics": topics,
            "word_count": len(text.split()),
            "sentence_count": len(re.findall(r'[.!?]', text))
        }

    except Exception as e:
        return {"summary": f"Erreur résumé: {e}", "key_topics": []}
