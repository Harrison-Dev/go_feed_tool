"""
PTT Viral Prediction FastAPI Service

Lightweight inference service for predicting viral posts.
Designed to run on VPS with minimal resources (1 vCPU, 1GB RAM).
"""

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import xgboost as xgb

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from training.feature_engineering import FEATURE_NAMES

app = FastAPI(
    title="PTT Viral Predictor",
    description="Predict probability of PTT articles becoming viral",
    version="1.0.0",
)

# Global model instance
model: Optional[xgb.XGBClassifier] = None


class PredictRequest(BaseModel):
    """Request schema for single article prediction"""

    board: str
    title: str
    post_time: str
    comments_15min: int
    push_15min: int
    boo_15min: int
    hour_of_day: int
    day_of_week: int
    title_length: int
    has_image: bool
    tag_type: str


class PredictResponse(BaseModel):
    """Response schema for prediction"""

    probability: float


class BatchPredictRequest(BaseModel):
    """Request schema for batch prediction"""

    articles: list[PredictRequest]


class BatchPredictResponse(BaseModel):
    """Response schema for batch prediction"""

    predictions: list[PredictResponse]


class HealthResponse(BaseModel):
    """Response schema for health check"""

    status: str
    model_loaded: bool


def load_model():
    """Load the XGBoost model from file"""
    global model

    if model is not None:
        return

    # Try multiple model paths
    model_paths = [
        Path(__file__).parent.parent / "models" / "viral_predictor_final.json",
        Path(__file__).parent.parent / "models" / "viral_predictor.json",
        Path("/app/models/viral_predictor.json"),  # Docker path
    ]

    for model_path in model_paths:
        if model_path.exists():
            model = xgb.XGBClassifier()
            model.load_model(str(model_path))
            print(f"Model loaded from: {model_path}")
            return

    raise FileNotFoundError(f"Model file not found in any of: {model_paths}")


def request_to_features(req: PredictRequest) -> list:
    """Convert prediction request to feature vector"""
    # Calculate derived features
    total_15min = req.push_15min + req.boo_15min
    push_ratio_15min = req.push_15min / total_15min if total_15min > 0 else 0.5
    comment_velocity = req.comments_15min / 15.0

    # Map to feature vector in correct order
    features = {
        "comments_15min": req.comments_15min,
        "push_15min": req.push_15min,
        "boo_15min": req.boo_15min,
        "push_ratio_15min": push_ratio_15min,
        "comment_velocity": comment_velocity,
        "hour_of_day": req.hour_of_day,
        "day_of_week": req.day_of_week,
        "is_weekend": req.day_of_week >= 5,
        "is_prime_time": 18 <= req.hour_of_day <= 23,
        "title_length": req.title_length,
        "has_tag": bool(req.tag_type),
        "has_image": req.has_image,
        "content_length": 0,  # Not provided in request, use default
    }

    # Convert to vector in FEATURE_NAMES order
    vector = []
    for name in FEATURE_NAMES:
        value = features.get(name, 0)
        if isinstance(value, bool):
            value = int(value)
        vector.append(value)

    return vector


@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    try:
        load_model()
    except FileNotFoundError as e:
        print(f"Warning: {e}")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(status="ok", model_loaded=model is not None)


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """Predict viral probability for a single article"""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    features = request_to_features(req)
    prob = model.predict_proba([features])[0][1]

    return PredictResponse(probability=float(prob))


@app.post("/predict/batch", response_model=BatchPredictResponse)
async def predict_batch(req: BatchPredictRequest):
    """Predict viral probability for multiple articles"""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    predictions = []
    for article in req.articles:
        features = request_to_features(article)
        prob = model.predict_proba([features])[0][1]
        predictions.append(PredictResponse(probability=float(prob)))

    return BatchPredictResponse(predictions=predictions)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
