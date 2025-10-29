# Exemple de Quiz Généré

## 📝 Quiz: Introduction à Django

**Nombre de questions**: 5  
**Type**: Questions à choix multiples (QCM)  
**Options par question**: 4 (A, B, C, D)

---

### Question 1
**The objective of the course is to teach _____ development.**

- A) Django ✓
- B) framework
- C) template  
- D) database

**Réponse correcte**: A - Django

---

### Question 2
**Students will learn views, templates, _____ and deployments.**

- A) webapp
- B) models ✓
- C) framework
- D) course

**Réponse correcte**: B - models

---

### Question 3
**By the end, students can build a _____.**

- A) Django
- B) templates
- C) webapp ✓
- D) models

**Réponse correcte**: C - webapp

---

### Question 4
**This is a sample _____ document.**

- A) development
- B) Django
- C) course ✓
- D) students

**Réponse correcte**: C - course

---

### Question 5
**Students will learn _____, templates, models and deployments.**

- A) views ✓
- B) webapp
- C) Django
- D) course

**Réponse correcte**: A - views

---

## 📊 Statistiques

- **Total de questions**: 5
- **Mots-clés extraits**: Django, development, students, course, views, templates, models, webapp, deployments
- **Distracteurs générés**: 15 (3 par question)
- **Phrases sources**: Analysées automatiquement depuis le PDF

## 🎯 Comment ça fonctionne

1. **Extraction**: Le texte est extrait du PDF
2. **Analyse**: Les mots-clés les plus importants sont identifiés
3. **Génération**: Pour chaque mot-clé, une phrase est transformée en question
4. **Distracteurs**: Des options plausibles mais incorrectes sont ajoutées
5. **Randomisation**: L'ordre des options est mélangé

## 🖼️ Interface Visuelle

```
┌─────────────────────────────────────────────────────────┐
│  📝 Quiz Généré                                    ✕    │
├─────────────────────────────────────────────────────────┤
│  📊 5 questions générées automatiquement à partir du PDF│
│                                                         │
│  [ Afficher les réponses correctes ]     [Afficher]    │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 1  The objective of the course is to teach _____ │  │
│  │    development.                                   │  │
│  │                                                   │  │
│  │  ○ A. Django                                      │  │
│  │  ○ B. framework                                   │  │
│  │  ○ C. template                                    │  │
│  │  ○ D. database                                    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  [Autres questions...]                                  │
│                                                         │
│  [ 🎯 Corriger le quiz ]                                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                          [Fermer]       │
└─────────────────────────────────────────────────────────┘
```

## ✅ Mode Correction

Quand l'utilisateur clique sur "Corriger le quiz":

```
┌──────────────────────────────────────────────────┐
│ 1  The objective of the course is to teach _____ │
│    development.                                   │
│                                                   │
│  ● A. Django ✓ Correct                           │
│  ○ B. framework                                   │
│  ○ C. template                                    │
│  ○ D. database                                    │
│                                                   │
│  ┌────────────────────────────────────────────┐  │
│  │ ✓ Réponse correcte: A. Django              │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## 💡 Avantages du Format Quiz

1. **Interactif**: L'utilisateur peut tester ses connaissances
2. **Auto-correction**: Feedback immédiat
3. **Pédagogique**: Les distracteurs aident à comprendre le contexte
4. **Professionnels**: Format standard reconnu
5. **Flexible**: Facile à exporter ou partager

## 🔧 Paramètres Personnalisables

```python
# Dans program/views.py
questions = generate_questions_from_text(
    pdf_path=temp_pdf_path,
    num_questions=10  # Nombre de questions à générer
)
```

## 📱 Responsive

L'interface s'adapte automatiquement aux différentes tailles d'écran:
- Desktop: Modal large (max-w-3xl)
- Tablet: Modal moyen
- Mobile: Plein écran avec scroll

## 🎨 Personnalisation des Couleurs

- **Couleur principale**: `esprit-red` (#c8102e)
- **Correct**: Vert (#10b981)
- **Incorrect**: Rouge (#ef4444)
- **Neutre**: Gris (#6b7280)
