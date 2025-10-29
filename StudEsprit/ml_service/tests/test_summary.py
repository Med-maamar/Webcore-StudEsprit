import pytest
from ml_service import generator


def test_generate_summary_from_text(monkeypatch):
    """Test that summary generation works with sample text."""
    sample = (
        "This is a sample course document about Django development. "
        "Django is a high-level Python web framework that encourages rapid development. "
        "It follows the model-template-view architectural pattern. "
        "Students will learn how to build web applications using Django. "
        "The course covers models, views, templates, and URL routing. "
        "By the end of the course, students will be able to create full-stack web applications. "
        "Django provides an ORM for database interactions. "
        "The framework includes many built-in features like authentication and admin interface. "
        "Students will also learn about deployment strategies. "
        "The course emphasizes best practices and clean code principles."
    )

    def fake_extract(path):
        return sample

    monkeypatch.setattr(generator, 'extract_text_from_pdf', fake_extract)
    
    # Generate summary
    result = generator.generate_summary_from_text('/tmp/fake.pdf', num_sentences=3)
    
    # Verify structure
    assert isinstance(result, dict)
    assert 'summary' in result
    assert 'word_count' in result
    assert 'sentence_count' in result
    assert 'key_topics' in result
    assert 'summary_length' in result
    
    # Verify content
    assert isinstance(result['summary'], str)
    assert len(result['summary']) > 0
    assert result['word_count'] > 0
    assert result['sentence_count'] > 0
    assert isinstance(result['key_topics'], list)
    assert result['summary_length'] == 3  # We requested 3 sentences
    
    # Verify key topics are extracted
    assert len(result['key_topics']) > 0
    
    print(f"\n✓ Summary generated successfully:")
    print(f"  - Word count: {result['word_count']}")
    print(f"  - Sentence count: {result['sentence_count']}")
    print(f"  - Summary length: {result['summary_length']} sentences")
    print(f"  - Key topics: {result['key_topics']}")
    print(f"  - Summary: {result['summary'][:100]}...")
