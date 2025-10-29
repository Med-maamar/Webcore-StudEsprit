# Format de Quiz - Documentation

## Vue d'ensemble

Le générateur de tests produit maintenant des **questions à choix multiples (QCM)** au lieu de simples questions à trou. Chaque question comporte 4 options (A, B, C, D) avec une seule réponse correcte.

## Structure d'une Question

Chaque question générée contient les champs suivants:

```python
{
    'question': 'The objective of the course is to teach _____ development.',
    'options': {
        'A': 'Django',      # Réponse correcte
        'B': 'framework',   # Distracteur
        'C': 'template',    # Distracteur
        'D': 'database'     # Distracteur
    },
    'correct_answer': 'A',           # Lettre de la bonne réponse
    'answer_text': 'Django',         # Texte de la bonne réponse
    'source': 'The objective of...'  # Phrase source du PDF
}
```

## Algorithme de Génération

### 1. Extraction du Texte
- Le PDF est analysé avec PyPDF2
- Le texte est extrait page par page

### 2. Identification des Mots-Clés
- Tokenisation avec NLTK
- Filtrage des mots vides (stopwords)
- Sélection des mots les plus fréquents

### 3. Création des Questions
Pour chaque mot-clé:
- Recherche d'une phrase contenant ce mot
- Masquage du mot-clé avec `_____`
- Génération de 3 distracteurs (mauvaises réponses)

### 4. Génération des Distracteurs
Les distracteurs sont choisis parmi:
- Mots de longueur similaire au mot correct
- Autres mots significatifs du document
- Options génériques si nécessaire

### 5. Randomisation
- Les options (A, B, C, D) sont mélangées
- L'ordre de présentation est aléatoire
- La position de la réponse correcte varie

## Interface Utilisateur

Le template `_cours_tests_modal.html` affiche:

### Mode Quiz
- ✅ Questions numérotées avec badges colorés
- 🔘 Options radio pour sélectionner les réponses
- 🎯 Bouton "Corriger le quiz"
- 📊 Compteur de questions

### Mode Correction
- ✓ Réponses correctes surlignées en vert
- ❌ Réponses sélectionnées mais incorrectes
- 💡 Indication de la bonne réponse pour chaque question
- 🔄 Possibilité de masquer/afficher les réponses

## Fonctionnalités Interactives (Alpine.js)

```javascript
x-data="{
  showAnswers: false,      // Afficher/masquer les corrections
  userAnswers: {}          // Stocker les réponses de l'utilisateur
}"
```

### Toggle des Réponses
```html
<button @click="showAnswers = !showAnswers">
  <span x-text="showAnswers ? 'Masquer' : 'Afficher'"></span>
</button>
```

### Surlignage Conditionnel
```html
:class="showAnswers && letter === correct_answer ? 
        'border-green-500 bg-green-50' : 
        'border-gray-200'"
```

## Exemple d'Utilisation

### Depuis Django
```python
from ml_service.generator import generate_questions_from_text

questions = generate_questions_from_text(
    pdf_path='/path/to/course.pdf',
    num_questions=5
)

# Sauvegarder dans MongoDB
cours_collection.update_one(
    {'_id': ObjectId(cour_id)},
    {'$set': {'generated_tests': questions}}
)
```

### Format de Réponse
```python
[
    {
        'question': 'Students will learn views, templates, _____ and deployments.',
        'options': {
            'A': 'models',
            'B': 'framework',
            'C': 'database',
            'D': 'webapp'
        },
        'correct_answer': 'A',
        'answer_text': 'models',
        'source': 'Students will learn views, templates, models and deployments.'
    },
    # ... plus de questions
]
```

## Améliorations Futures Possibles

1. **Types de Questions Variés**
   - Questions Vrai/Faux
   - Associations
   - Réponses courtes

2. **Difficultés Variables**
   - Facile: distracteurs très différents
   - Moyen: distracteurs similaires
   - Difficile: distracteurs très proches

3. **Scoring Automatique**
   - Calcul du score total
   - Pourcentage de réussite
   - Feedback personnalisé

4. **Export**
   - Export en PDF
   - Export en JSON
   - Partage par lien

## Tests Unitaires

Le test vérifie:
```python
def test_generate_questions_from_text_simple(monkeypatch):
    # Chaque question doit avoir:
    assert 'question' in q        # La question avec _____
    assert 'options' in q          # Dictionnaire A/B/C/D
    assert 'correct_answer' in q   # Lettre A-D
    assert 'answer_text' in q      # Texte de la réponse
    
    # Vérifications de structure:
    assert isinstance(q['options'], dict)
    assert q['correct_answer'] in ['A', 'B', 'C', 'D']
    assert q['answer_text'] in q['options'].values()
```

## Performance

- **Temps de génération**: ~1-3 secondes pour 5 questions
- **Dépendance NLTK**: téléchargement initial requis (punkt, stopwords)
- **Taille mémoire**: dépend de la taille du PDF

## Compatibilité

- ✅ Python 3.8+
- ✅ Django 4.x
- ✅ NLTK 3.x
- ✅ PyPDF2 3.x (ou pypdf 3.x)
- ✅ Alpine.js 3.x (frontend)
