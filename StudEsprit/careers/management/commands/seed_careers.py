from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from careers.models import Opportunity


OPPORTUNITY_SEED = [
    {
        "company": "DataForge Labs",
        "role": "Junior Data Engineer",
        "location": "Remote - EU",
        "skills": ["python", "pandas", "mongodb", "docker"],
        "apply_url": "https://example.com/jobs/data-engineer",
        "description": "Work with a small analytics team to build robust data pipelines for edtech partners.",
    },
    {
        "company": "CloudRise",
        "role": "Django Backend Developer",
        "location": "Paris, France",
        "skills": ["django", "rest", "aws", "git"],
        "apply_url": "https://example.com/jobs/django",
        "description": "Build APIs powering our learning platform, collaborate with frontend teams, and ship weekly releases.",
    },
    {
        "company": "NeoBank Junior",
        "role": "Full Stack Developer",
        "location": "Tunis, Tunisia",
        "skills": ["python", "django", "react", "htmx"],
        "apply_url": "https://example.com/jobs/fullstack",
        "description": "Create delightful financial experiences for students using lean, modern web stacks.",
    },
    {
        "company": "Insight AI",
        "role": "Machine Learning Intern",
        "location": "Remote",
        "skills": ["python", "ml", "nlp", "pandas"],
        "apply_url": "https://example.com/jobs/ml-intern",
        "description": "Support the applied research team with NLP experimentation and model evaluation.",
    },
    {
        "company": "Scripted",
        "role": "Technical Writer",
        "location": "Lyon, France",
        "skills": ["git", "rest", "python"],
        "apply_url": "https://example.com/jobs/writer",
        "description": "Translate complex developer guides into concise tutorials for our student audience.",
    },
    {
        "company": "BlockForge",
        "role": "DevOps Apprentice",
        "location": "Remote",
        "skills": ["docker", "linux", "aws", "git"],
        "apply_url": "https://example.com/jobs/devops",
        "description": "Own CI/CD pipelines, improve observability, and learn from senior platform engineers.",
    },
    {
        "company": "Nimbus Learning",
        "role": "Product Analyst",
        "location": "Remote - Africa",
        "skills": ["pandas", "python", "rest"],
        "apply_url": "https://example.com/jobs/analyst",
        "description": "Partner with product squads to translate raw data into actionable insights.",
    },
    {
        "company": "Aurora XR",
        "role": "XR Content Developer",
        "location": "Berlin, Germany",
        "skills": ["python", "react", "graphql"],
        "apply_url": "https://example.com/jobs/xr",
        "description": "Prototype XR learning simulations blending narrative with interactive scenarios.",
    },
    {
        "company": "Open Scholars",
        "role": "Community Manager",
        "location": "Remote",
        "skills": ["git", "python", "htmx"],
        "apply_url": "https://example.com/jobs/community",
        "description": "Foster open-source student communities, curate challenges, and mentor newcomers.",
    },
    {
        "company": "ZenPay",
        "role": "QA Automation Engineer",
        "location": "Marseille, France",
        "skills": ["python", "rest", "docker"],
        "apply_url": "https://example.com/jobs/qa",
        "description": "Automate regression tests across services, ensuring reliable payment experiences.",
    },
]


class Command(BaseCommand):
    help = "Seed the careers module with demo opportunities"

    def handle(self, *args, **options):
        created = 0
        for seed in OPPORTUNITY_SEED:
            if Opportunity.objects(company=seed["company"], role=seed["role"]).first():
                continue
            deadline = timezone.now() + timedelta(days=random.randint(14, 60))
            opportunity = Opportunity(
                company=seed["company"],
                role=seed["role"],
                location=seed["location"],
                skills=seed["skills"],
                apply_url=seed["apply_url"],
                deadline=deadline,
                description=seed["description"],
                is_active=True,
            )
            opportunity.save()
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} opportunity records."))
