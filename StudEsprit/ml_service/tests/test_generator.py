import os
import tempfile
from ml_service import generator


def test_generate_questions_from_text_simple(monkeypatch):
    sample = (
        "This is a sample course document.\n"
        "The objective of the course is to teach Django development.\n"
        "Students will learn views, templates, models and deployments.\n"
        "By the end, students can build a webapp.\n"
    )

    def fake_extract(path):
        return sample

    monkeypatch.setattr(generator, 'extract_text_from_pdf', fake_extract)
    qs = generator.generate_questions_from_text('/tmp/fake.pdf', num_questions=3)
    assert isinstance(qs, list)
    assert len(qs) >= 1
    for q in qs:
        assert 'question' in q
        assert 'options' in q
        assert 'correct_answer' in q
        assert 'answer_text' in q
        # Verify options structure
        assert isinstance(q['options'], dict)
        assert 'A' in q['options']
        assert 'B' in q['options']
        assert 'C' in q['options']
        assert 'D' in q['options']
        # Verify correct answer is one of A, B, C, D
        assert q['correct_answer'] in ['A', 'B', 'C', 'D']
        # Verify the correct answer text is in the options
        assert q['answer_text'] in q['options'].values()
