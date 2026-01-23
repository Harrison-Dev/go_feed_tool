"""
Tests for Model Training module - TDD approach
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestDataPreparation:
    """Tests for preparing training data."""

    def test_loads_articles_from_json(self, tmp_path):
        """Should load articles from JSON file."""
        from train_model import load_dataset

        data = [
            {"article_id": "M.1", "title": "Test", "is_viral": True},
            {"article_id": "M.2", "title": "Test2", "is_viral": False},
        ]
        json_file = tmp_path / "test.json"
        with open(json_file, "w") as f:
            json.dump(data, f)

        articles = load_dataset(str(json_file))

        assert len(articles) == 2

    def test_splits_by_time(self, tmp_path):
        """Should split data by time to prevent data leakage."""
        from train_model import time_split

        articles = [
            {"post_time": "2025-11-01T10:00:00", "is_viral": True},
            {"post_time": "2025-11-15T10:00:00", "is_viral": False},
            {"post_time": "2025-12-01T10:00:00", "is_viral": True},
            {"post_time": "2025-12-15T10:00:00", "is_viral": False},
        ]

        train, test = time_split(articles, split_date="2025-12-01")

        assert len(train) == 2
        assert len(test) == 2
        assert all(a["post_time"] < "2025-12-01" for a in train)


class TestFeatureExtraction:
    """Tests for extracting features for training."""

    def test_extracts_features_and_labels(self):
        """Should extract X (features) and y (labels) from articles."""
        from train_model import prepare_training_data

        articles = [
            {
                "article_id": "M.1",
                "title": "[閒聊] Test",
                "post_time": "2026-01-22T10:00:00",
                "content": "content",
                "comments": [],
                "is_viral": True,
            },
            {
                "article_id": "M.2",
                "title": "[問卦] Test2",
                "post_time": "2026-01-22T11:00:00",
                "content": "content2",
                "comments": [],
                "is_viral": False,
            },
        ]

        X, y = prepare_training_data(articles)

        assert len(X) == 2
        assert len(y) == 2
        assert y[0] == 1  # True -> 1
        assert y[1] == 0  # False -> 0


class TestModelTraining:
    """Tests for XGBoost model training."""

    def test_trains_xgboost_classifier(self):
        """Should train XGBoost binary classifier."""
        from train_model import train_model
        import numpy as np

        # Simple training data
        X = np.array([
            [5, 3, 1, 0.75, 0.33, 10, 3, 0, 0, 15, 1, 0, 100],
            [0, 0, 0, 0.5, 0.0, 14, 0, 0, 0, 10, 1, 0, 50],
            [10, 8, 2, 0.8, 0.67, 20, 5, 1, 1, 20, 1, 1, 200],
            [1, 1, 0, 1.0, 0.07, 9, 1, 0, 0, 12, 0, 0, 80],
        ])
        y = np.array([1, 0, 1, 0])

        model = train_model(X, y)

        # Should be able to predict
        predictions = model.predict(X)
        assert len(predictions) == 4
        assert all(p in [0, 1] for p in predictions)

    def test_returns_probabilities(self):
        """Should return probability scores."""
        from train_model import train_model
        import numpy as np

        X = np.array([
            [5, 3, 1, 0.75, 0.33, 10, 3, 0, 0, 15, 1, 0, 100],
            [0, 0, 0, 0.5, 0.0, 14, 0, 0, 0, 10, 1, 0, 50],
            [10, 8, 2, 0.8, 0.67, 20, 5, 1, 1, 20, 1, 1, 200],
            [1, 1, 0, 1.0, 0.07, 9, 1, 0, 0, 12, 0, 0, 80],
        ])
        y = np.array([1, 0, 1, 0])

        model = train_model(X, y)
        probs = model.predict_proba(X)

        assert probs.shape == (4, 2)
        assert all(0 <= p <= 1 for row in probs for p in row)


class TestModelSaving:
    """Tests for model persistence."""

    def test_saves_model_to_json(self, tmp_path):
        """Should save model in JSON format."""
        from train_model import train_model, save_model
        import numpy as np

        X = np.array([[1, 2, 3, 0.5, 0.1, 10, 3, 0, 0, 15, 1, 0, 100]] * 4)
        y = np.array([1, 0, 1, 0])

        model = train_model(X, y)
        model_path = tmp_path / "model.json"

        save_model(model, str(model_path))

        assert model_path.exists()
        assert model_path.stat().st_size > 0

    def test_loads_saved_model(self, tmp_path):
        """Should load model from JSON file."""
        from train_model import train_model, save_model, load_model
        import numpy as np

        X = np.array([[1, 2, 3, 0.5, 0.1, 10, 3, 0, 0, 15, 1, 0, 100]] * 4)
        y = np.array([1, 0, 1, 0])

        model = train_model(X, y)
        model_path = tmp_path / "model.json"
        save_model(model, str(model_path))

        loaded_model = load_model(str(model_path))

        # Should produce same predictions
        original_pred = model.predict(X)
        loaded_pred = loaded_model.predict(X)

        assert list(original_pred) == list(loaded_pred)
