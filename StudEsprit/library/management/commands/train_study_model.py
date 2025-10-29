from django.core.management.base import BaseCommand
import os
import json

class Command(BaseCommand):
    help = 'Build dataset from study_profiles and train the personalized study model'

    def handle(self, *args, **options):
        try:
            from ml_service.personalized_training import build_dataset, train_model
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to import training module: {e}"))
            return

        self.stdout.write('Building dataset...')
        df = build_dataset()
        if df.empty:
            self.stdout.write(self.style.WARNING('No training data found (dataset is empty). Ensure documents are processed and study profiles exist.'))
            return

        data_dir = os.path.join('ml_service', 'data')
        model_dir = os.path.join('ml_service', 'models')
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(model_dir, exist_ok=True)

        csv_path = os.path.join(data_dir, 'personalized_dataset.csv')
        model_path = os.path.join(model_dir, 'personalized_model.pkl')

        df.to_csv(csv_path, index=False)
        self.stdout.write(f"Saved dataset to {csv_path}")

        self.stdout.write('Training model...')
        metrics = train_model(df=df, save_model_path=model_path)
        self.stdout.write(self.style.SUCCESS(f"Training completed. Metrics: {json.dumps(metrics)}"))
        self.stdout.write(self.style.SUCCESS(f"Model saved to {model_path}"))
