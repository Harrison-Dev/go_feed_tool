"""
Feature Engineering for PTT Viral Post Prediction

Extracts features from article data for model training and inference.
"""

import re
from datetime import datetime, timedelta
from typing import Optional


def parse_comment_time(post_time_str: str, comment_time_str: str) -> Optional[datetime]:
    """
    Parse comment time relative to post time.

    Comment time format: "MM/DD HH:MM"
    Post time format: ISO format "YYYY-MM-DDTHH:MM:SS"

    Handles year boundary (Dec 31 -> Jan 1).
    """
    if not comment_time_str:
        return None

    try:
        post_dt = datetime.fromisoformat(post_time_str)
        # Parse MM/DD HH:MM
        month_day, time_part = comment_time_str.split(" ")
        month, day = map(int, month_day.split("/"))
        hour, minute = map(int, time_part.split(":"))

        # Assume same year as post
        comment_dt = post_dt.replace(month=month, day=day, hour=hour, minute=minute, second=0)

        # Handle year boundary: if comment appears to be before post but in different month
        # (e.g., post Dec 31, comment Jan 1), adjust year
        if comment_dt < post_dt - timedelta(days=1):
            comment_dt = comment_dt.replace(year=post_dt.year + 1)

        return comment_dt
    except (ValueError, AttributeError):
        return None


def calc_comments_15min(post_time: str, comments: list[dict]) -> int:
    """Count comments within 15 minutes of post time."""
    post_dt = datetime.fromisoformat(post_time)
    cutoff = post_dt + timedelta(minutes=15)

    count = 0
    for comment in comments:
        comment_time = comment.get("time")
        if not comment_time:
            continue

        comment_dt = parse_comment_time(post_time, comment_time)
        if comment_dt and comment_dt <= cutoff:
            count += 1

    return count


def calc_push_boo_15min(post_time: str, comments: list[dict]) -> tuple[int, int]:
    """Count push and boo within 15 minutes of post time."""
    post_dt = datetime.fromisoformat(post_time)
    cutoff = post_dt + timedelta(minutes=15)

    push_count = 0
    boo_count = 0

    for comment in comments:
        comment_time = comment.get("time")
        if not comment_time:
            continue

        comment_dt = parse_comment_time(post_time, comment_time)
        if comment_dt and comment_dt <= cutoff:
            comment_type = comment.get("type", "")
            if comment_type == "推":
                push_count += 1
            elif comment_type == "噓":
                boo_count += 1

    return push_count, boo_count


def calc_comment_velocity(comments_15min: int) -> float:
    """Calculate comments per minute in first 15 minutes."""
    return comments_15min / 15.0


def extract_time_features(post_time: str) -> dict:
    """Extract time-based features from post time."""
    dt = datetime.fromisoformat(post_time)

    return {
        "hour_of_day": dt.hour,
        "day_of_week": dt.weekday(),  # 0=Monday, 6=Sunday
        "is_weekend": dt.weekday() >= 5,  # Saturday=5, Sunday=6
        "is_prime_time": 18 <= dt.hour <= 23,
    }


def extract_text_features(title: str, content: str) -> dict:
    """Extract text-based features from title and content."""
    # Check for [標籤] pattern
    tag_match = re.search(r"\[([^\]]+)\]", title)
    has_tag = tag_match is not None
    tag_type = tag_match.group(1) if tag_match else ""

    # Check for imgur link
    has_image = "imgur.com" in content or "imgur.com" in title

    return {
        "title_length": len(title),
        "has_tag": has_tag,
        "tag_type": tag_type,
        "has_image": has_image,
        "content_length": len(content),
    }


def extract_features(article: dict) -> dict:
    """
    Extract all features from an article dictionary.

    Returns a dict with all feature values.
    """
    post_time = article.get("post_time", "")
    comments = article.get("comments", [])
    title = article.get("title", "")
    content = article.get("content", "")

    # Early interaction features (15 min window)
    comments_15min = calc_comments_15min(post_time, comments)
    push_15min, boo_15min = calc_push_boo_15min(post_time, comments)
    total_15min = push_15min + boo_15min
    push_ratio_15min = push_15min / total_15min if total_15min > 0 else 0.5
    comment_velocity = calc_comment_velocity(comments_15min)

    # Time features
    time_features = extract_time_features(post_time) if post_time else {
        "hour_of_day": 0,
        "day_of_week": 0,
        "is_weekend": False,
        "is_prime_time": False,
    }

    # Text features
    text_features = extract_text_features(title, content)

    return {
        # Early interaction
        "comments_15min": comments_15min,
        "push_15min": push_15min,
        "boo_15min": boo_15min,
        "push_ratio_15min": push_ratio_15min,
        "comment_velocity": comment_velocity,
        # Time features
        **time_features,
        # Text features
        **text_features,
    }


# Feature names in order for model input
FEATURE_NAMES = [
    "comments_15min",
    "push_15min",
    "boo_15min",
    "push_ratio_15min",
    "comment_velocity",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_prime_time",
    "title_length",
    "has_tag",
    "has_image",
    "content_length",
]


def get_feature_vector(features: dict) -> list:
    """
    Convert feature dict to numeric vector for model input.

    Converts booleans to int (0/1).
    Excludes tag_type (categorical - would need encoding).
    """
    vector = []
    for name in FEATURE_NAMES:
        value = features.get(name, 0)
        # Convert bool to int
        if isinstance(value, bool):
            value = int(value)
        vector.append(value)
    return vector
