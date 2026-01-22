"""
Tests for PTT Viral Prediction FastAPI Service
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import numpy as np


class TestPredictEndpoint:
    """Test /predict endpoint"""

    def test_predict_returns_probability(self, client):
        """POST /predict should return probability between 0 and 1"""
        request_data = {
            "board": "C_Chat",
            "title": "[閒聊] 今天的動畫好好看",
            "post_time": "2026-01-22T20:00:00",
            "comments_15min": 10,
            "push_15min": 8,
            "boo_15min": 1,
            "hour_of_day": 20,
            "day_of_week": 3,
            "title_length": 15,
            "has_image": True,
            "tag_type": "閒聊",
        }

        response = client.post("/predict", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert "probability" in data
        assert 0.0 <= data["probability"] <= 1.0

    def test_predict_high_engagement_returns_high_prob(self, client):
        """Article with high early engagement should have higher probability"""
        high_engagement = {
            "board": "C_Chat",
            "title": "[爆卦] 大新聞",
            "post_time": "2026-01-22T20:00:00",
            "comments_15min": 50,
            "push_15min": 45,
            "boo_15min": 2,
            "hour_of_day": 20,
            "day_of_week": 3,
            "title_length": 10,
            "has_image": False,
            "tag_type": "爆卦",
        }

        response = client.post("/predict", json=high_engagement)
        data = response.json()

        # High engagement should give decent probability
        assert data["probability"] >= 0.3

    def test_predict_low_engagement_returns_low_prob(self, client):
        """Article with low early engagement should have lower probability"""
        low_engagement = {
            "board": "C_Chat",
            "title": "[問題] 請問一下",
            "post_time": "2026-01-22T04:00:00",
            "comments_15min": 1,
            "push_15min": 0,
            "boo_15min": 0,
            "hour_of_day": 4,
            "day_of_week": 1,
            "title_length": 8,
            "has_image": False,
            "tag_type": "問題",
        }

        response = client.post("/predict", json=low_engagement)
        data = response.json()

        # Low engagement should give lower probability
        assert data["probability"] < 0.7

    def test_predict_missing_required_field(self, client):
        """Should return 422 for missing required fields"""
        incomplete_data = {
            "board": "C_Chat",
            "title": "Test",
            # Missing other required fields
        }

        response = client.post("/predict", json=incomplete_data)
        assert response.status_code == 422


class TestHealthEndpoint:
    """Test /health endpoint"""

    def test_health_returns_ok(self, client):
        """GET /health should return ok status"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_model_info(self, client):
        """GET /health should return model information"""
        response = client.get("/health")

        data = response.json()
        assert "model_loaded" in data
        assert data["model_loaded"] is True


class TestBatchPredict:
    """Test /predict/batch endpoint"""

    def test_batch_predict_multiple_articles(self, client):
        """POST /predict/batch should handle multiple articles"""
        articles = [
            {
                "board": "C_Chat",
                "title": "[閒聊] Test 1",
                "post_time": "2026-01-22T20:00:00",
                "comments_15min": 10,
                "push_15min": 8,
                "boo_15min": 1,
                "hour_of_day": 20,
                "day_of_week": 3,
                "title_length": 12,
                "has_image": False,
                "tag_type": "閒聊",
            },
            {
                "board": "Stock",
                "title": "[標的] Test 2",
                "post_time": "2026-01-22T10:00:00",
                "comments_15min": 5,
                "push_15min": 3,
                "boo_15min": 1,
                "hour_of_day": 10,
                "day_of_week": 3,
                "title_length": 12,
                "has_image": False,
                "tag_type": "標的",
            },
        ]

        response = client.post("/predict/batch", json={"articles": articles})

        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert len(data["predictions"]) == 2
        for pred in data["predictions"]:
            assert 0.0 <= pred["probability"] <= 1.0


# Fixtures
@pytest.fixture
def client():
    """Create test client with mocked model"""
    # Import here to avoid circular imports
    from predict_service import app, load_model

    # Ensure model is loaded
    load_model()

    return TestClient(app)
