# ml_service/generator.py
import fitz  # PyMuPDF
import openai
import os

# Set your OpenAI key (from Render env vars)
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_questions_from_text(pdf_path):
    """
    Extract text from PDF → Send to OpenAI → Return questions
    """
    # 1. Extract text
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    if not text.strip():
        return [{"question": "No text found in PDF", "answer": "Check file"}]

    # 2. Call OpenAI
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a quiz generator. Create 5 multiple-choice questions from the text. Format: Q1: ..., Options: A)..., B)..., Answer: A"},
                {"role": "user", "content": f"Text: {text[:3000]}"}
            ],
            max_tokens=500
        )
        raw = response.choices[0].message.content

        # 3. Parse into list
        questions = []
        for line in raw.split('\n'):
            if line.strip() and ('Q' in line or 'Question' in line):
                questions.append({
                    "question": line.strip(),
                    "answer": "See options"
                })
        return questions or [{"question": raw, "answer": "AI response"}]

    except Exception as e:
        return [{"question": "AI Error", "answer": str(e)}]
