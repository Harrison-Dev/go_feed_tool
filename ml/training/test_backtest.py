"""
Tests for Backtest System - TDD approach
"""

import pytest
import numpy as np


class TestBacktestMetrics:
    """Tests for backtest evaluation metrics."""

    def test_calculates_precision_at_threshold(self):
        """Should calculate precision for predictions above threshold."""
        from backtest import calc_precision

        y_true = [1, 1, 0, 0, 1]
        y_prob = [0.9, 0.8, 0.7, 0.3, 0.6]

        # At threshold 0.7: predictions are [1, 1, 1, 0, 0]
        # True positives: 2, False positives: 1
        # Precision = 2/3 = 0.667
        precision = calc_precision(y_true, y_prob, threshold=0.7)

        assert precision == pytest.approx(2/3, rel=0.01)

    def test_calculates_recall_at_threshold(self):
        """Should calculate recall for predictions above threshold."""
        from backtest import calc_recall

        y_true = [1, 1, 0, 0, 1]
        y_prob = [0.9, 0.8, 0.7, 0.3, 0.6]

        # At threshold 0.7: predictions are [1, 1, 1, 0, 0]
        # True positives: 2, False negatives: 1
        # Recall = 2/3 = 0.667
        recall = calc_recall(y_true, y_prob, threshold=0.7)

        assert recall == pytest.approx(2/3, rel=0.01)


class TestBacktestReport:
    """Tests for backtest report generation."""

    def test_generates_report_dict(self):
        """Should generate report with all metrics."""
        from backtest import generate_report

        y_true = np.array([1, 1, 0, 0, 1])
        y_prob = np.array([0.9, 0.8, 0.7, 0.3, 0.6])

        report = generate_report(y_true, y_prob, threshold=0.7)

        assert "total_articles" in report
        assert "actual_viral" in report
        assert "predicted_viral" in report
        assert "precision" in report
        assert "recall" in report
        assert "threshold" in report

    def test_includes_confusion_counts(self):
        """Should include true/false positive/negative counts."""
        from backtest import generate_report

        y_true = np.array([1, 1, 0, 0, 1])
        y_prob = np.array([0.9, 0.8, 0.7, 0.3, 0.6])

        report = generate_report(y_true, y_prob, threshold=0.7)

        assert "true_positives" in report
        assert "false_positives" in report
        assert "false_negatives" in report


class TestFeatureImportance:
    """Tests for feature importance extraction."""

    def test_extracts_feature_importance(self):
        """Should extract feature importance from trained model."""
        from backtest import get_feature_importance
        from train_model import train_model
        from feature_engineering import FEATURE_NAMES

        X = np.array([
            [5, 3, 1, 0.75, 0.33, 10, 3, 0, 0, 15, 1, 0, 100],
            [0, 0, 0, 0.5, 0.0, 14, 0, 0, 0, 10, 1, 0, 50],
            [10, 8, 2, 0.8, 0.67, 20, 5, 1, 1, 20, 1, 1, 200],
            [1, 1, 0, 1.0, 0.07, 9, 1, 0, 0, 12, 0, 0, 80],
        ])
        y = np.array([1, 0, 1, 0])

        model = train_model(X, y)
        importance = get_feature_importance(model, FEATURE_NAMES)

        # Should return list of (feature_name, importance) tuples
        assert len(importance) == len(FEATURE_NAMES)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in importance)
        # Should be sorted by importance descending
        assert importance[0][1] >= importance[-1][1]


class TestBacktestRunner:
    """Tests for running backtest on test data."""

    def test_runs_backtest_and_returns_results(self, tmp_path):
        """Should run backtest on test articles and return results."""
        from backtest import run_backtest
        from train_model import train_model, save_model
        import json

        # Create test data
        articles = [
            {
                "article_id": "M.1",
                "title": "[閒聊] High engagement",
                "post_time": "2026-01-22T10:00:00",
                "content": "content https://imgur.com/test",
                "comments": [
                    {"time": "01/22 10:05", "type": "推"},
                    {"time": "01/22 10:06", "type": "推"},
                    {"time": "01/22 10:07", "type": "推"},
                ],
                "push_count": 120,
                "boo_count": 10,
                "is_viral": True,
            },
            {
                "article_id": "M.2",
                "title": "[問卦] Low engagement",
                "post_time": "2026-01-22T11:00:00",
                "content": "content",
                "comments": [],
                "push_count": 5,
                "boo_count": 2,
                "is_viral": False,
            },
        ]

        # Train a simple model
        X = np.array([
            [3, 3, 0, 1.0, 0.2, 10, 3, 0, 0, 20, 1, 1, 30],
            [0, 0, 0, 0.5, 0.0, 11, 3, 0, 0, 18, 1, 0, 7],
        ])
        y = np.array([1, 0])

        model = train_model(X, y)
        model_path = tmp_path / "model.json"
        save_model(model, str(model_path))

        # Run backtest
        results = run_backtest(articles, str(model_path), threshold=0.5)

        assert "report" in results
        assert "predictions" in results
        assert len(results["predictions"]) == 2
