from django.core.management.base import BaseCommand
from library.models import CommunityService
from core.mongo import get_db
from bson import ObjectId
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Initialize community with sample posts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing community posts before adding sample data',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing community posts...')
            db = get_db()
            db.community_posts.delete_many({})
            self.stdout.write(
                self.style.SUCCESS('Successfully cleared community posts')
            )

        # Sample posts data
        sample_posts = [
            {
                'title': 'Comment bien organiser ses révisions pour les examens ?',
                'content': '''Salut tout le monde ! 

Je passe mes examens dans quelques semaines et je me demande comment bien organiser mes révisions. J'ai beaucoup de matières à réviser et je ne sais pas par où commencer.

Est-ce que vous avez des conseils pour :
- Organiser un planning de révisions efficace ?
- Gérer le stress avant les examens ?
- Techniques de mémorisation qui marchent ?

Merci d'avance pour vos conseils ! 🙏''',
                'category': 'question',
                'tags': ['examens', 'révisions', 'organisation', 'conseils']
            },
            {
                'title': 'Mon expérience avec Django - Projet de fin d\'année',
                'content': '''Bonjour la communauté !

Je viens de terminer mon projet de fin d'année en utilisant Django et je voulais partager mon expérience avec vous.

**Ce que j'ai appris :**
- Django est vraiment puissant pour créer des applications web rapidement
- Le système de modèles est génial pour gérer la base de données
- Les vues basées sur les classes sont très pratiques

**Les défis rencontrés :**
- Configuration initiale un peu complexe
- Gestion des migrations au début
- Déploiement sur Heroku

**Mes conseils :**
- Commencez par suivre le tutoriel officiel Django
- Utilisez Django REST Framework pour les APIs
- N'hésitez pas à utiliser les packages de la communauté

Si vous avez des questions sur Django, n'hésitez pas ! 😊''',
                'category': 'experience',
                'tags': ['django', 'python', 'projet', 'web', 'expérience']
            },
            {
                'title': 'Conseils pour réussir en programmation',
                'content': '''Hey les codeurs ! 👨‍💻

Après 2 ans d'études en informatique, voici mes conseils pour bien progresser en programmation :

**1. Codez tous les jours**
Même 30 minutes par jour, c'est mieux que 5h une fois par semaine.

**2. Lisez du code**
Regardez les projets open source sur GitHub, c'est une mine d'or !

**3. Ne copiez pas bêtement**
Comprenez ce que vous faites, sinon vous n'apprendrez rien.

**4. Faites des projets personnels**
C'est le meilleur moyen d'appliquer ce que vous apprenez.

**5. N'ayez pas peur de l'erreur**
Les erreurs sont normales, c'est comme ça qu'on apprend !

**6. Participez à la communauté**
Stack Overflow, forums, Discord... N'hésitez pas à poser des questions !

Quels sont vos conseils à vous ? 🤔''',
                'category': 'tip',
                'tags': ['programmation', 'conseils', 'apprentissage', 'développement']
            },
            {
                'title': 'Problème avec MongoDB et Django - Aide SVP !',
                'content': '''Salut ! J'ai un problème avec MongoDB dans mon projet Django.

**Mon setup :**
- Django 4.2
- PyMongo 4.0
- MongoDB Atlas

**Le problème :**
Quand j'essaie de sauvegarder un document, j'ai cette erreur :
```
TypeError: Object of type 'datetime' is not JSON serializable
```

**Mon code :**
```python
from datetime import datetime
from pymongo import MongoClient

client = MongoClient(MONGODB_URI)
db = client.mydb
collection = db.documents

document = {
    'title': 'Mon document',
    'created_at': datetime.now(),
    'content': 'Contenu...'
}

collection.insert_one(document)  # Erreur ici !
```

Est-ce que quelqu'un peut m'aider ? Je suis bloqué depuis 2 jours ! 😅

Merci d'avance ! 🙏''',
                'category': 'help',
                'tags': ['mongodb', 'django', 'python', 'erreur', 'aide']
            },
            {
                'title': 'Discussion : Quel langage choisir pour débuter ?',
                'content': '''Salut la communauté ! 

Je vois souvent cette question sur les forums : "Quel langage de programmation choisir pour débuter ?"

**Les options populaires :**
- Python : Simple, beaucoup de ressources
- JavaScript : Partout sur le web
- Java : Très utilisé en entreprise
- C++ : Plus complexe mais puissant

**Mon avis :**
Je pense que Python est le meilleur pour débuter car :
- Syntaxe claire et lisible
- Beaucoup de tutoriels
- Utilisé dans plein de domaines (web, data science, IA...)
- Communauté très active

**Mais attention :**
Le choix dépend aussi de ce que vous voulez faire ! Si vous voulez faire du web frontend, JavaScript est plus logique.

**Votre avis ?**
Quel langage recommanderiez-vous à un débutant ? Et pourquoi ?

Hâte de lire vos réponses ! 😊''',
                'category': 'discussion',
                'tags': ['programmation', 'débutant', 'langages', 'discussion', 'conseils']
            }
        ]

        # Get a sample user ID (you might want to use a real user ID)
        db = get_db()
        users = list(db.users.find().limit(1))
        if not users:
            self.stdout.write(
                self.style.ERROR('No users found in database. Please create a user first.')
            )
            return

        sample_user_id = str(users[0]['_id'])

        self.stdout.write('Creating sample community posts...')

        for i, post_data in enumerate(sample_posts):
            # Add some randomness to creation dates
            days_ago = random.randint(1, 30)
            created_at = datetime.utcnow() - timedelta(days=days_ago)
            
            # Create post
            post_id = CommunityService.create_post(
                user_id=sample_user_id,
                title=post_data['title'],
                content=post_data['content'],
                category=post_data['category'],
                tags=post_data['tags']
            )

            # Update creation date to make it more realistic
            db.community_posts.update_one(
                {'_id': ObjectId(post_id)},
                {'$set': {'created_at': created_at}}
            )

            # Add some random likes and views
            random_likes = random.randint(0, 15)
            random_views = random.randint(5, 50)
            
            # Add random likes (using the same user for simplicity)
            likes = [ObjectId(sample_user_id)] * random_likes
            db.community_posts.update_one(
                {'_id': ObjectId(post_id)},
                {'$set': {'likes': likes, 'views': random_views}}
            )

            self.stdout.write(f'  ✓ Created post: {post_data["title"]}')

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {len(sample_posts)} sample community posts!')
        )
        self.stdout.write(
            self.style.SUCCESS('You can now visit /library/community/ to see the community in action!')
        )
