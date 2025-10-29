# 📄 Génération Automatique de Résumés

## Vue d'ensemble

Le système génère automatiquement des résumés des cours à partir de leurs PDFs en utilisant une technique d'**extraction de phrases clés** (extractive summarization). Cette approche sélectionne les phrases les plus importantes du document original.

---

## 🎯 Fonctionnalités

### 1. Génération de Résumé
- **Analyse du PDF**: Extraction du texte complet
- **Identification des mots-clés**: Détection des termes les plus fréquents
- **Scoring des phrases**: Évaluation de l'importance de chaque phrase
- **Sélection intelligente**: Choix des N phrases les plus représentatives
- **Ordre cohérent**: Maintien de l'ordre original pour la lisibilité

### 2. Statistiques Automatiques
- **Nombre de mots**: Comptage total dans le document
- **Nombre de phrases**: Phrases détectées dans le document
- **Longueur du résumé**: Nombre de phrases sélectionnées
- **Sujets principaux**: Top 5 des mots-clés extraits

### 3. Interface Utilisateur
- **Modal élégant**: Affichage dans une fenêtre modale responsive
- **Cartes statistiques**: Visualisation des métriques
- **Tags de sujets**: Affichage des mots-clés principaux
- **Bouton d'impression**: Export facile du résumé

---

## 🔬 Algorithme de Génération

### Étape 1: Extraction du Texte
```python
text = extract_text_from_pdf(pdf_path)
```
- Lecture du PDF avec PyPDF2
- Extraction page par page
- Concaténation du texte

### Étape 2: Tokenisation
```python
sentences = sent_tokenize(text)
words = word_tokenize(text)
```
- Découpage en phrases avec NLTK
- Découpage en mots pour l'analyse

### Étape 3: Filtrage des Mots
```python
filtered_words = [w for w in words 
                  if w not in stopwords 
                  and len(w) > 3]
```
- Suppression des mots vides (stopwords)
- Suppression des mots trop courts
- Focus sur les termes significatifs

### Étape 4: Calcul des Fréquences
```python
word_freq = Counter(filtered_words)
top_keywords = word_freq.most_common(10)
```
- Comptage de la fréquence de chaque mot
- Sélection des 10 mots les plus fréquents

### Étape 5: Scoring des Phrases
```python
for sentence in sentences:
    score = sum(word_freq[word] for word in sentence)
    normalized_score = score / len(sentence_words)
```
- Score basé sur la fréquence des mots
- Normalisation par la longueur de la phrase
- Évite le biais vers les phrases longues

### Étape 6: Sélection des Phrases
```python
top_sentences = sorted(scored_sentences)[:num_sentences]
top_sentences = sorted(top_sentences, key=original_order)
```
- Sélection des N meilleures phrases
- Tri par ordre d'apparition original
- Maintien de la cohérence narrative

---

## 📊 Structure de Sortie

```python
{
    'summary': 'This is a sample course document about Django development. Students will learn how to build web applications. The course covers models, views, templates.',
    'word_count': 99,
    'sentence_count': 10,
    'key_topics': ['django', 'course', 'students', 'development', 'framework'],
    'summary_length': 3
}
```

### Champs du Résumé

| Champ | Type | Description |
|-------|------|-------------|
| `summary` | string | Texte du résumé (phrases sélectionnées) |
| `word_count` | int | Nombre total de mots dans le document |
| `sentence_count` | int | Nombre total de phrases dans le document |
| `key_topics` | list | Top 5 des mots-clés les plus fréquents |
| `summary_length` | int | Nombre de phrases dans le résumé |

---

## 🎨 Interface Utilisateur

### Boutons dans le Tableau des Cours
```html
<!-- Générer un nouveau résumé -->
<button hx-post="/program/cours/generate_summary/{{ cour_id }}/">
  📄 Générer résumé
</button>

<!-- Voir un résumé existant -->
<button hx-get="/program/cours/view_summary/{{ cour_id }}/">
  👁️ Voir résumé
</button>
```

### Modal de Résumé
- **En-tête**: Titre avec icône
- **Info cours**: Nom du cours
- **Statistiques**: 3 cartes (mots, phrases, résumé)
- **Sujets**: Tags colorés pour les mots-clés
- **Résumé**: Texte justifié dans un cadre
- **Info**: Note explicative sur la génération
- **Actions**: Boutons Imprimer et Fermer

---

## 🔧 Utilisation

### 1. Depuis l'Interface Web

1. **Aller sur la page des cours**
   ```
   /program/cours/
   ```

2. **Cliquer sur "Générer résumé"**
   - Le système analyse le PDF
   - Génère le résumé automatiquement
   - Sauvegarde dans MongoDB
   - Affiche le modal avec le résultat

3. **Consulter un résumé existant**
   - Cliquer sur "Voir résumé"
   - Affiche le résumé sauvegardé

### 2. Depuis le Code Python

```python
from ml_service.generator import generate_summary_from_text

# Générer un résumé
summary_data = generate_summary_from_text(
    pdf_path='/path/to/document.pdf',
    num_sentences=5  # Nombre de phrases souhaitées
)

# Accéder aux données
print(f"Résumé: {summary_data['summary']}")
print(f"Mots-clés: {summary_data['key_topics']}")
print(f"Statistiques: {summary_data['word_count']} mots")
```

### 3. Depuis Django Views

```python
# Dans program/views.py
def cour_generate_summary(request, cid):
    # Récupérer le cours
    c = services.get_cour(cid)
    
    # Générer le résumé
    summary_data = ml_generator.generate_summary_from_text(
        pdf_path, 
        num_sentences=5
    )
    
    # Sauvegarder
    services.update_cour(cid, {
        'generated_summary': summary_data
    })
    
    # Afficher
    return render(request, '_cours_summary_modal.html', {
        'summary_data': summary_data
    })
```

---

## 📈 Paramètres Personnalisables

### Longueur du Résumé
```python
# Résumé court (3 phrases)
generate_summary_from_text(pdf_path, num_sentences=3)

# Résumé moyen (5 phrases)
generate_summary_from_text(pdf_path, num_sentences=5)

# Résumé long (10 phrases)
generate_summary_from_text(pdf_path, num_sentences=10)
```

### Nombre de Mots-clés
Modifiez dans `generator.py`:
```python
top_keywords = [w for w, _ in word_freq.most_common(10)]  # 10 mots
```

---

## ✅ Tests Unitaires

### Test de Génération
```python
def test_generate_summary_from_text(monkeypatch):
    # Mock PDF extraction
    monkeypatch.setattr(generator, 'extract_text_from_pdf', fake_extract)
    
    # Generate summary
    result = generator.generate_summary_from_text('/tmp/fake.pdf', num_sentences=3)
    
    # Verify structure
    assert 'summary' in result
    assert 'word_count' in result
    assert 'sentence_count' in result
    assert 'key_topics' in result
    assert result['summary_length'] == 3
```

### Exécuter les Tests
```bash
pytest -v ml_service/tests/test_summary.py
```

**Résultat attendu:**
```
✓ Summary generated successfully:
  - Word count: 99
  - Sentence count: 10
  - Summary length: 3 sentences
  - Key topics: ['course', 'django', 'students', 'development', 'framework']
```

---

## 🎓 Avantages et Limites

### ✅ Avantages

1. **Rapide**: Traitement en quelques secondes
2. **Pas de hallucination**: Phrases réelles du document
3. **Fidèle au contenu**: Pas d'interprétation ou modification
4. **Multilingue**: Fonctionne avec n'importe quelle langue
5. **Léger**: Ne nécessite pas de modèle lourd (pas de GPT)

### ⚠️ Limites

1. **Extraction simple**: Pas de reformulation
2. **Cohérence limitée**: Phrases peuvent manquer de transition
3. **Pas de synthèse**: Ne crée pas de nouvelles phrases
4. **Dépendant de la qualité**: Si le PDF contient peu de texte, résumé limité
5. **Pas d'analyse sémantique**: Basé uniquement sur la fréquence

---

## 🚀 Améliorations Futures

### 1. Résumé Abstractif avec IA
```python
# Utiliser un modèle GPT ou BART pour reformuler
from transformers import pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
abstract_summary = summarizer(text, max_length=130, min_length=30)
```

### 2. Support Multilingue Amélioré
- Détection automatique de la langue
- Stopwords adaptés à chaque langue
- Tokenisation spécifique

### 3. Résumé Structuré
- Extraction des titres et sections
- Génération d'un plan
- Résumé hiérarchique

### 4. Visualisations
- Nuage de mots-clés
- Graphique de fréquence
- Carte conceptuelle

### 5. Export Avancé
- Export PDF stylisé
- Export Word/DOCX
- Export Markdown

---

## 📚 Technologies Utilisées

- **PyPDF2**: Extraction du texte des PDFs
- **NLTK**: Tokenisation et stopwords
- **Python Collections.Counter**: Comptage de fréquences
- **Django**: Framework web et gestion des vues
- **HTMX**: Chargement dynamique des modals
- **Tailwind CSS**: Styling moderne et responsive

---

## 💡 Cas d'Usage

### Pour les Étudiants
- Obtenir rapidement une vue d'ensemble d'un cours
- Réviser les points clés avant un examen
- Créer des fiches de révision

### Pour les Enseignants
- Vérifier la cohérence du contenu
- Identifier les concepts principaux couverts
- Créer des descriptions de cours

### Pour l'Administration
- Cataloguer les cours
- Créer des résumés pour les brochures
- Analyser le contenu pédagogique

---

## 🔗 Ressources

- [Documentation NLTK](https://www.nltk.org/)
- [PyPDF2 Documentation](https://pypdf2.readthedocs.io/)
- [Extractive Summarization](https://en.wikipedia.org/wiki/Automatic_summarization#Extractive_summarization)
- [Text Mining with Python](https://www.nltk.org/book/)

---

## 📞 Support

Pour toute question ou amélioration, consultez:
- La documentation du projet
- Les tests unitaires dans `ml_service/tests/`
- Le code source dans `ml_service/generator.py`
