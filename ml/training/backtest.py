"""
Backtest System for PTT Viral Post Prediction

Evaluates model performance on historical data.
"""

import numpy as np
from typing import Optional

from feature_engineering import extract_features, get_feature_vector, FEATURE_NAMES
from train_model import load_model


def calc_precision(y_true: list, y_prob: list, threshold: float) -> float:
    """Calculate precision at a given probability threshold."""
    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    true_positives = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    predicted_positives = sum(y_pred)

    if predicted_positives == 0:
        return 0.0
    return true_positives / predicted_positives


def calc_recall(y_true: list, y_prob: list, threshold: float) -> float:
    """Calculate recall at a given probability threshold."""
    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    true_positives = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    actual_positives = sum(y_true)

    if actual_positives == 0:
        return 0.0
    return true_positives / actual_positives


def generate_report(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict:
    """
    Generate backtest report with all metrics.

    Args:
        y_true: Actual labels
        y_prob: Predicted probabilities
        threshold: Decision threshold

    Returns:
        Report dictionary with metrics
    """
    y_pred = (y_prob >= threshold).astype(int)

    true_positives = int(np.sum((y_true == 1) & (y_pred == 1)))
    false_positives = int(np.sum((y_true == 0) & (y_pred == 1)))
    false_negatives = int(np.sum((y_true == 1) & (y_pred == 0)))
    true_negatives = int(np.sum((y_true == 0) & (y_pred == 0)))

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0

    return {
        "threshold": threshold,
        "total_articles": len(y_true),
        "actual_viral": int(np.sum(y_true)),
        "predicted_viral": int(np.sum(y_pred)),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "precision": precision,
        "recall": recall,
    }


def get_feature_importance(model, feature_names: list) -> list[tuple[str, float]]:
    """
    Extract feature importance from trained model.

    Returns:
        List of (feature_name, importance) tuples sorted by importance descending
    """
    importances = model.feature_importances_
    importance_list = list(zip(feature_names, importances))
    return sorted(importance_list, key=lambda x: x[1], reverse=True)


def run_backtest(articles: list[dict], model_path: str, threshold: float = 0.7) -> dict:
    """
    Run backtest on test articles.

    Args:
        articles: List of article dicts with is_viral label
        model_path: Path to trained model
        threshold: Decision threshold

    Returns:
        Dict with report and individual predictions
    """
    model = load_model(model_path)

    # Extract features and labels
    X = []
    y_true = []
    for article in articles:
        features = extract_features(article)
        vector = get_feature_vector(features)
        X.append(vector)
        y_true.append(1 if article.get("is_viral") else 0)

    X = np.array(X)
    y_true = np.array(y_true)

    # Get predictions
    y_prob = model.predict_proba(X)[:, 1]

    # Generate report
    report = generate_report(y_true, y_prob, threshold)

    # Individual predictions
    predictions = []
    for i, article in enumerate(articles):
        predictions.append({
            "article_id": article.get("article_id"),
            "title": article.get("title"),
            "predicted_prob": float(y_prob[i]),
            "actual_viral": bool(y_true[i]),
            "predicted_viral": bool(y_prob[i] >= threshold),
        })

    return {
        "report": report,
        "predictions": predictions,
        "feature_importance": get_feature_importance(model, FEATURE_NAMES),
    }


def print_report(results: dict):
    """Print formatted backtest report."""
    report = results["report"]

    print("=" * 60)
    print("PTT 爆文預測模型 - 回測報告")
    print("=" * 60)
    print(f"測試文章數: {report['total_articles']}")
    print(f"實際爆文數: {report['actual_viral']}")
    print(f"門檻: P={report['threshold']}")
    print("-" * 60)
    print(f"預測爆文數: {report['predicted_viral']}")
    print(f"命中數 (TP): {report['true_positives']}")
    print(f"誤報數 (FP): {report['false_positives']}")
    print(f"漏報數 (FN): {report['false_negatives']}")
    print("-" * 60)
    print(f"Precision: {report['precision']:.2%}")
    print(f"Recall: {report['recall']:.2%}")
    print("-" * 60)
    print("特徵重要度 Top 5:")
    for i, (name, importance) in enumerate(results["feature_importance"][:5], 1):
        print(f"  {i}. {name}: {importance:.3f}")
    print("=" * 60)


def main():
    """Main backtest script."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run backtest on test data")
    parser.add_argument("--data", required=True, help="Path to test data JSON")
    parser.add_argument("--model", required=True, help="Path to trained model")
    parser.add_argument("--threshold", type=float, default=0.7, help="Decision threshold")
    parser.add_argument("--output", help="Optional output JSON for predictions")

    args = parser.parse_args()

    print(f"Loading data from {args.data}...")
    with open(args.data, "r", encoding="utf-8") as f:
        articles = json.load(f)

    print(f"Running backtest with threshold={args.threshold}...")
    results = run_backtest(articles, args.model, args.threshold)

    print_report(results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
