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


def calc_comments_in_window(post_time: str, comments: list[dict], minutes: int) -> int:
    """Count comments within specified minutes of post time."""
    if not post_time:
        return 0
    post_dt = datetime.fromisoformat(post_time)
    cutoff = post_dt + timedelta(minutes=minutes)

    count = 0
    for comment in comments:
        comment_time = comment.get("time")
        if not comment_time:
            continue

        comment_dt = parse_comment_time(post_time, comment_time)
        if comment_dt and comment_dt <= cutoff:
            count += 1

    return count


def calc_comments_15min(post_time: str, comments: list[dict]) -> int:
    """Count comments within 15 minutes of post time."""
    return calc_comments_in_window(post_time, comments, 15)


def calc_comments_5min(post_time: str, comments: list[dict]) -> int:
    """Count comments within 5 minutes of post time."""
    return calc_comments_in_window(post_time, comments, 5)


def calc_velocity_ratio(comments_early: int, comments_window: int) -> float:
    """
    計算加速度比率: 早期佔比。

    比率高 = 早期爆發力強
    比率低 = 慢熱型
    """
    if comments_window == 0:
        return 0.0
    return comments_early / comments_window


# Supported time windows
SUPPORTED_WINDOWS = [5, 10, 15]

# Early window for velocity ratio (always use half of the main window, minimum 2 minutes)
def get_early_window(main_window: int) -> int:
    """Get early window size for velocity ratio calculation."""
    return max(2, main_window // 2)


def calc_push_boo_in_window(post_time: str, comments: list[dict], minutes: int) -> tuple[int, int]:
    """Count push and boo within specified minutes of post time."""
    if not post_time:
        return 0, 0
    post_dt = datetime.fromisoformat(post_time)
    cutoff = post_dt + timedelta(minutes=minutes)

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


def calc_push_boo_15min(post_time: str, comments: list[dict]) -> tuple[int, int]:
    """Count push and boo within 15 minutes of post time."""
    return calc_push_boo_in_window(post_time, comments, 15)


def calc_comment_velocity(comments_count: int, minutes: int) -> float:
    """Calculate comments per minute in the given time window."""
    return comments_count / float(minutes)


def extract_time_features(post_time: str) -> dict:
    """Extract time-based features from post time."""
    if not post_time:
        return {
            "hour_of_day": 12,
            "day_of_week": 0,
            "is_weekend": False,
            "is_prime_time": False,
        }
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


def extract_features_with_window(article: dict, time_window: int = 15) -> dict:
    """
    Extract all features from an article dictionary with configurable time window.

    Args:
        article: Article dictionary with post_time, comments, title, content
        time_window: Time window in minutes (5, 10, or 15)

    Returns a dict with all feature values.
    """
    post_time = article.get("post_time", "")
    comments = article.get("comments", [])
    title = article.get("title", "")
    content = article.get("content", "")

    # Early interaction features (configurable window)
    early_window = get_early_window(time_window)
    comments_window = calc_comments_in_window(post_time, comments, time_window)
    comments_early = calc_comments_in_window(post_time, comments, early_window)
    push_window, boo_window = calc_push_boo_in_window(post_time, comments, time_window)
    total_window = push_window + boo_window
    push_ratio = push_window / total_window if total_window > 0 else 0.5
    comment_velocity = calc_comment_velocity(comments_window, time_window)
    velocity_ratio = calc_velocity_ratio(comments_early, comments_window)

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
        # Early interaction (named with window suffix for clarity)
        f"comments_{time_window}min": comments_window,
        f"comments_{early_window}min": comments_early,
        f"push_{time_window}min": push_window,
        f"boo_{time_window}min": boo_window,
        f"push_ratio_{time_window}min": push_ratio,
        "comment_velocity": comment_velocity,
        "velocity_ratio": velocity_ratio,
        # Time features
        **time_features,
        # Text features
        **text_features,
    }


def extract_features(article: dict) -> dict:
    """
    Extract all features from an article dictionary (default 15-min window).

    Returns a dict with all feature values.
    """
    # Use 15-min window for backward compatibility
    return extract_features_with_window(article, time_window=15)


def get_feature_names(time_window: int = 15) -> list[str]:
    """
    Get feature names for the specified time window.

    Args:
        time_window: Time window in minutes (5, 10, or 15)

    Returns:
        List of feature names in order for model input
    """
    early_window = get_early_window(time_window)
    return [
        f"comments_{time_window}min",
        f"comments_{early_window}min",
        f"push_{time_window}min",
        f"boo_{time_window}min",
        f"push_ratio_{time_window}min",
        "comment_velocity",
        "velocity_ratio",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "is_prime_time",
        "title_length",
        "has_tag",
        "has_image",
        "content_length",
    ]


# Default feature names for backward compatibility (15-min window)
FEATURE_NAMES = get_feature_names(15)


def get_feature_vector(features: dict, time_window: int = 15) -> list:
    """
    Convert feature dict to numeric vector for model input.

    Args:
        features: Feature dictionary
        time_window: Time window in minutes (default 15)

    Converts booleans to int (0/1).
    Excludes tag_type (categorical - would need encoding).
    """
    feature_names = get_feature_names(time_window)
    vector = []
    for name in feature_names:
        value = features.get(name, 0)
        # Convert bool to int
        if isinstance(value, bool):
            value = int(value)
        vector.append(value)
    return vector
