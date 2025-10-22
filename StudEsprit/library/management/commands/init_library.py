"""
Management command to initialize library collections and indexes.
"""

from django.core.management.base import BaseCommand
from core.mongo import ensure_indexes


class Command(BaseCommand):
    help = 'Initialize library collections and indexes'

    def handle(self, *args, **options):
        self.stdout.write('Initializing library collections and indexes...')
        
        try:
            ensure_indexes()
            self.stdout.write(
                self.style.SUCCESS('Successfully initialized library collections and indexes')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error initializing library: {e}')
            )
