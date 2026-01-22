"""
Model Training for PTT Viral Post Prediction

Trains XGBoost classifier on extracted features.
"""

import json
from pathlib import Path

import numpy as np
import xgboost as xgb

from feature_engineering import extract_features, get_feature_vector


def load_dataset(file_path: str) -> list[dict]:
    """Load articles from JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def time_split(articles: list[dict], split_date: str) -> tuple[list[dict], list[dict]]:
    """
    Split articles by time to prevent data leakage.

    Args:
        articles: List of article dicts with post_time
        split_date: ISO format date string for split point

    Returns:
        (train_articles, test_articles)
    """
    train = [a for a in articles if a.get("post_time", "") < split_date]
    test = [a for a in articles if a.get("post_time", "") >= split_date]
    return train, test


def prepare_training_data(articles: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract features and labels from articles.

    Returns:
        (X, y) where X is feature matrix and y is label array
    """
    X = []
    y = []

    for article in articles:
        features = extract_features(article)
        vector = get_feature_vector(features)
        X.append(vector)
        y.append(1 if article.get("is_viral") else 0)

    return np.array(X), np.array(y)


def train_model(X: np.ndarray, y: np.ndarray) -> xgb.XGBClassifier:
    """
    Train XGBoost binary classifier.

    Args:
        X: Feature matrix (n_samples, n_features)
        y: Labels (n_samples,)

    Returns:
        Trained XGBClassifier
    """
    # 計算類別權重: non-viral數量 / viral數量
    neg_count = np.sum(y == 0)
    pos_count = np.sum(y == 1)
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        objective="binary:logistic",
        eval_metric="logloss",
        use_label_encoder=False,
        scale_pos_weight=scale_pos_weight,  # 處理類別不平衡
    )
    model.fit(X, y)
    return model


def save_model(model: xgb.XGBClassifier, path: str):
    """Save model to JSON file."""
    model.save_model(path)


def load_model(path: str) -> xgb.XGBClassifier:
    """Load model from JSON file."""
    model = xgb.XGBClassifier()
    model.load_model(path)
    return model


def main():
    """Main training script."""
    import argparse

    parser = argparse.ArgumentParser(description="Train viral post prediction model")
    parser.add_argument("--data", required=True, help="Path to training data JSON")
    parser.add_argument("--output", default="../models/viral_predictor.json", help="Output model path")
    parser.add_argument("--split-date", default="2025-12-01", help="Train/test split date")

    args = parser.parse_args()

    print(f"Loading data from {args.data}...")
    articles = load_dataset(args.data)
    print(f"Loaded {len(articles)} articles")

    print(f"Splitting at {args.split_date}...")
    train_articles, test_articles = time_split(articles, args.split_date)
    print(f"Train: {len(train_articles)}, Test: {len(test_articles)}")

    print("Preparing training data...")
    X_train, y_train = prepare_training_data(train_articles)
    X_test, y_test = prepare_training_data(test_articles)

    print(f"Training features shape: {X_train.shape}")
    print(f"Viral ratio in train: {y_train.mean():.2%}")

    print("Training model...")
    model = train_model(X_train, y_train)

    # Evaluate
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    print("\n=== Test Results ===")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.2%}")
    print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.2%}")
    print(f"Recall: {recall_score(y_test, y_pred, zero_division=0):.2%}")
    if len(np.unique(y_test)) > 1:
        print(f"AUC: {roc_auc_score(y_test, y_prob):.3f}")

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_model(model, str(output_path))
    print(f"\nModel saved to {output_path}")


if __name__ == "__main__":
    main()
