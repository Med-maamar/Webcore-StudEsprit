import json
import sys
import os

from ml_service.personalized_training import build_dataset, train_model

if __name__ == '__main__':
    try:
        df = build_dataset()
        os.makedirs('ml_service/models', exist_ok=True)
        os.makedirs('ml_service/data', exist_ok=True)
        if not df.empty:
            df.to_csv('ml_service/data/personalized_dataset.csv', index=False)
        else:
            print(json.dumps({'status': 'no_data', 'n_rows': len(df)}))
            sys.exit(0)
        metrics = train_model(df=df, save_model_path='ml_service/models/personalized_model.pkl')
        print(json.dumps({'status': 'ok', 'metrics': metrics, 'n_rows': len(df)}))
    except Exception as e:
        print(json.dumps({'status': 'error', 'message': str(e)}))
        sys.exit(1)
