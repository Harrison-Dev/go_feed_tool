"""
PTT Viral Prediction FastAPI Service

Lightweight inference service for predicting viral posts.
Designed to run on VPS with minimal resources (1 vCPU, 1GB RAM).
"""

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import AliasChoices, BaseModel, Field
import numpy as np
import xgboost as xgb

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from training.feature_engineering import get_feature_names, get_early_window, SUPPORTED_WINDOWS

# Time window configuration (default 10 minutes, can be set via env var)
TIME_WINDOW = int(os.environ.get("PREDICTION_TIME_WINDOW", "10"))
if TIME_WINDOW not in SUPPORTED_WINDOWS:
    raise ValueError(f"TIME_WINDOW must be one of {SUPPORTED_WINDOWS}, got {TIME_WINDOW}")

EARLY_WINDOW = get_early_window(TIME_WINDOW)
FEATURE_NAMES = get_feature_names(TIME_WINDOW)

app = FastAPI(
    title="PTT Viral Predictor",
    description=f"Predict probability of PTT articles becoming viral (using {TIME_WINDOW}-min window)",
    version="2.0.0",
)

# Global model instance
model: Optional[xgb.XGBClassifier] = None


def window_aliases(metric: str) -> AliasChoices:
    """Accept current generic fields and legacy time-window-specific fields."""
    return AliasChoices(
        f"{metric}_window",
        *(f"{metric}_{window}min" for window in SUPPORTED_WINDOWS),
    )


class PredictRequest(BaseModel):
    """Request schema for single article prediction"""

    board: str
    title: str
    post_time: str
    # Window-based metrics (use whatever window the server is configured for)
    comments_window: int = Field(validation_alias=window_aliases("comments"))
    push_window: int = Field(validation_alias=window_aliases("push"))
    boo_window: int = Field(validation_alias=window_aliases("boo"))
    # Optional: early window metrics for velocity ratio (estimated if not provided)
    comments_early: Optional[int] = None
    # Time features
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

    model_config = {"protected_namespaces": ()}

    status: str
    model_loaded: bool
    time_window: int
    early_window: int


def load_model():
    """Load the XGBoost model from file"""
    global model

    if model is not None:
        return

    # Try multiple model paths (prefer time-window-specific model)
    model_paths = [
        Path(__file__).parent.parent / "models" / f"viral_predictor_{TIME_WINDOW}min.json",
        Path(__file__).parent.parent / "models" / "viral_predictor_final.json",
        Path(__file__).parent.parent / "models" / "viral_predictor.json",
        Path(f"/app/models/viral_predictor_{TIME_WINDOW}min.json"),  # Docker path
        Path("/app/models/viral_predictor_final.json"),  # Docker path fallback
        Path("/app/models/viral_predictor.json"),  # Docker path fallback
    ]

    for model_path in model_paths:
        if model_path.exists():
            estimator = xgb.XGBClassifier()
            # XGBoost 2.0+ does not set _estimator_type until after fit; loading a saved
            # model requires priming the attribute to avoid TypeError during load_model.
            if not getattr(estimator, "_estimator_type", None):
                estimator._estimator_type = "classifier"

            try:
                estimator.load_model(str(model_path))
            except TypeError:
                estimator._estimator_type = "classifier"
                estimator.load_model(str(model_path))

            # Manually restore minimal sklearn attributes required for predict_proba
            estimator.__dict__["n_classes_"] = 2
            estimator.__dict__["classes_"] = np.array([0, 1])

            model = estimator
            print(f"Model loaded from: {model_path} (TIME_WINDOW={TIME_WINDOW}min)")
            return

    raise FileNotFoundError(f"Model file not found in any of: {model_paths}")


def request_to_features(req: PredictRequest) -> list:
    """Convert prediction request to feature vector"""
    # Calculate derived features
    total_window = req.push_window + req.boo_window
    push_ratio = req.push_window / total_window if total_window > 0 else 0.5
    comment_velocity = req.comments_window / float(TIME_WINDOW)

    # Estimate early window comments if not provided
    # (assume linear distribution, scale by early_window/time_window)
    if req.comments_early is not None:
        comments_early = req.comments_early
    else:
        comments_early = int(req.comments_window * (EARLY_WINDOW / TIME_WINDOW))

    velocity_ratio = comments_early / req.comments_window if req.comments_window > 0 else 0.0

    # Map to feature vector in correct order (using dynamic feature names)
    features = {
        f"comments_{TIME_WINDOW}min": req.comments_window,
        f"comments_{EARLY_WINDOW}min": comments_early,
        f"push_{TIME_WINDOW}min": req.push_window,
        f"boo_{TIME_WINDOW}min": req.boo_window,
        f"push_ratio_{TIME_WINDOW}min": push_ratio,
        "comment_velocity": comment_velocity,
        "velocity_ratio": velocity_ratio,
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
    except Exception as e:
        print(f"Warning: Failed to load model: {e}")


@app.get("/health", response_model=HealthResponse)
async def health(response: Response):
    """Health check endpoint"""
    if model is None:
        response.status_code = 503

    return HealthResponse(
        status="ok" if model is not None else "model_unloaded",
        model_loaded=model is not None,
        time_window=TIME_WINDOW,
        early_window=EARLY_WINDOW,
    )


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
