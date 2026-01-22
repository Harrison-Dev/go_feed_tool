"""
Tests for Feature Engineering module - TDD approach
"""

import pytest
from datetime import datetime


class TestComments15Min:
    """Tests for extracting 15-minute early interaction features."""

    def test_counts_comments_within_15_minutes(self):
        """Should count only comments within 15 minutes of post time."""
        from feature_engineering import calc_comments_15min

        post_time = "2026-01-22T10:00:00"
        comments = [
            {"time": "01/22 10:05", "type": "推"},  # 5 min - included
            {"time": "01/22 10:14", "type": "推"},  # 14 min - included
            {"time": "01/22 10:15", "type": "推"},  # 15 min - included (boundary)
            {"time": "01/22 10:16", "type": "推"},  # 16 min - excluded
            {"time": "01/22 11:00", "type": "推"},  # 60 min - excluded
        ]

        result = calc_comments_15min(post_time, comments)

        assert result == 3

    def test_handles_missing_comment_times(self):
        """Should skip comments with None time."""
        from feature_engineering import calc_comments_15min

        post_time = "2026-01-22T10:00:00"
        comments = [
            {"time": "01/22 10:05", "type": "推"},
            {"time": None, "type": "推"},  # No time - skip
            {"time": "01/22 10:10", "type": "推"},
        ]

        result = calc_comments_15min(post_time, comments)

        assert result == 2

    def test_handles_year_boundary(self):
        """Should handle comments crossing year boundary (Dec 31 -> Jan 1)."""
        from feature_engineering import calc_comments_15min

        post_time = "2025-12-31T23:55:00"
        comments = [
            {"time": "12/31 23:58", "type": "推"},  # 3 min - included
            {"time": "01/01 00:05", "type": "推"},  # 10 min - included (next year)
            {"time": "01/01 00:20", "type": "推"},  # 25 min - excluded
        ]

        result = calc_comments_15min(post_time, comments)

        assert result == 2


class TestPushBoo15Min:
    """Tests for counting push/boo within 15 minutes."""

    def test_counts_push_within_15_minutes(self):
        """Should count only 推 within 15 minutes."""
        from feature_engineering import calc_push_boo_15min

        post_time = "2026-01-22T10:00:00"
        comments = [
            {"time": "01/22 10:05", "type": "推"},
            {"time": "01/22 10:10", "type": "噓"},
            {"time": "01/22 10:12", "type": "→"},
            {"time": "01/22 10:20", "type": "推"},  # excluded - after 15 min
        ]

        push, boo = calc_push_boo_15min(post_time, comments)

        assert push == 1
        assert boo == 1


class TestCommentVelocity:
    """Tests for comment velocity calculation."""

    def test_calculates_comments_per_minute(self):
        """Should calculate average comments per minute in first 15 min."""
        from feature_engineering import calc_comment_velocity

        # 6 comments in 15 minutes = 0.4 per minute
        comments_15min = 6

        result = calc_comment_velocity(comments_15min)

        assert result == pytest.approx(0.4)

    def test_returns_zero_for_no_comments(self):
        """Should return 0 when no comments."""
        from feature_engineering import calc_comment_velocity

        result = calc_comment_velocity(0)

        assert result == 0.0


class TestTimeFeatures:
    """Tests for time-based features."""

    def test_extracts_hour_of_day(self):
        """Should extract hour from post time."""
        from feature_engineering import extract_time_features

        post_time = "2026-01-22T14:30:00"

        features = extract_time_features(post_time)

        assert features["hour_of_day"] == 14

    def test_extracts_day_of_week(self):
        """Should extract day of week (0=Monday, 6=Sunday)."""
        from feature_engineering import extract_time_features

        # 2026-01-22 is Thursday
        post_time = "2026-01-22T14:30:00"

        features = extract_time_features(post_time)

        assert features["day_of_week"] == 3  # Thursday

    def test_detects_weekend(self):
        """Should detect weekend (Saturday/Sunday)."""
        from feature_engineering import extract_time_features

        saturday = "2026-01-24T14:30:00"
        monday = "2026-01-26T14:30:00"

        sat_features = extract_time_features(saturday)
        mon_features = extract_time_features(monday)

        assert sat_features["is_weekend"] == True
        assert mon_features["is_weekend"] == False

    def test_detects_prime_time(self):
        """Should detect prime time (18:00-23:59)."""
        from feature_engineering import extract_time_features

        prime_time = "2026-01-22T20:00:00"
        not_prime = "2026-01-22T10:00:00"

        prime_features = extract_time_features(prime_time)
        not_prime_features = extract_time_features(not_prime)

        assert prime_features["is_prime_time"] == True
        assert not_prime_features["is_prime_time"] == False


class TestTextFeatures:
    """Tests for text-based features."""

    def test_extracts_title_length(self):
        """Should calculate title length."""
        from feature_engineering import extract_text_features

        title = "[閒聊] 今天好熱"
        content = "內容"

        features = extract_text_features(title, content)

        assert features["title_length"] == len(title)

    def test_detects_tag_presence(self):
        """Should detect [標籤] in title."""
        from feature_engineering import extract_text_features

        with_tag = "[問卦] 有人知道嗎"
        without_tag = "沒有標籤的標題"

        features_with = extract_text_features(with_tag, "")
        features_without = extract_text_features(without_tag, "")

        assert features_with["has_tag"] == True
        assert features_without["has_tag"] == False

    def test_extracts_tag_type(self):
        """Should extract tag type from title."""
        from feature_engineering import extract_text_features

        features = extract_text_features("[問卦] 有人知道嗎", "")

        assert features["tag_type"] == "問卦"

    def test_detects_image_link(self):
        """Should detect imgur links in content."""
        from feature_engineering import extract_text_features

        with_image = "看這個 https://imgur.com/abc123"
        without_image = "純文字內容"

        features_with = extract_text_features("title", with_image)
        features_without = extract_text_features("title", without_image)

        assert features_with["has_image"] == True
        assert features_without["has_image"] == False

    def test_calculates_content_length(self):
        """Should calculate content length."""
        from feature_engineering import extract_text_features

        content = "這是一段內容文字"

        features = extract_text_features("title", content)

        assert features["content_length"] == len(content)


class TestExtractAllFeatures:
    """Tests for complete feature extraction."""

    def test_extracts_all_features_for_article(self):
        """Should extract all features from an article dict."""
        from feature_engineering import extract_features

        article = {
            "article_id": "M.1234",
            "board": "C_Chat",
            "title": "[閒聊] 測試文章",
            "author": "testuser",
            "post_time": "2026-01-22T10:00:00",
            "content": "內容 https://imgur.com/test",
            "comments": [
                {"time": "01/22 10:05", "type": "推", "user": "u1", "content": "推"},
                {"time": "01/22 10:10", "type": "噓", "user": "u2", "content": "噓"},
            ],
            "push_count": 50,
            "boo_count": 10,
            "neutral_count": 5,
            "is_viral": False
        }

        features = extract_features(article)

        # Early interaction features
        assert "comments_15min" in features
        assert "push_15min" in features
        assert "boo_15min" in features
        assert "push_ratio_15min" in features
        assert "comment_velocity" in features

        # Time features
        assert "hour_of_day" in features
        assert "day_of_week" in features
        assert "is_weekend" in features
        assert "is_prime_time" in features

        # Text features
        assert "title_length" in features
        assert "has_tag" in features
        assert "tag_type" in features
        assert "has_image" in features
        assert "content_length" in features

    def test_returns_feature_vector_for_model(self):
        """Should return numeric feature vector for model input."""
        from feature_engineering import extract_features, get_feature_vector

        article = {
            "article_id": "M.1234",
            "board": "C_Chat",
            "title": "[閒聊] 測試文章",
            "author": "testuser",
            "post_time": "2026-01-22T10:00:00",
            "content": "內容",
            "comments": [],
            "push_count": 50,
            "boo_count": 10,
            "neutral_count": 5,
            "is_viral": False
        }

        features = extract_features(article)
        vector = get_feature_vector(features)

        assert isinstance(vector, list)
        assert all(isinstance(v, (int, float)) for v in vector)
