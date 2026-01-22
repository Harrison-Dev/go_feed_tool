"""
Tests for PTT Crawler - TDD approach

Testing strategy:
- Use real HTTP responses where possible (recorded fixtures)
- Mock only the network layer, not the parsing logic
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from pathlib import Path


# We'll import the module once it exists
# from ptt_crawler import PTTCrawler, Article, Comment


class TestPTTCrawlerInit:
    """Tests for crawler initialization."""

    def test_crawler_sets_age_verification_cookie(self):
        """Crawler should set over18=1 cookie for age-gated boards."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()

        assert crawler.session.cookies.get("over18", domain=".ptt.cc") == "1"

    def test_crawler_sets_browser_like_user_agent(self):
        """Crawler should use browser-like User-Agent to avoid blocking."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()

        user_agent = crawler.session.headers.get("User-Agent")
        assert "Mozilla" in user_agent
        assert "Chrome" in user_agent or "Firefox" in user_agent


class TestParsePostTime:
    """Tests for post time parsing."""

    def test_parses_standard_ptt_time_format(self):
        """Should parse 'Fri Jan 22 10:00:00 2026' to ISO format."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        result = crawler._parse_post_time("Fri Jan 22 10:00:00 2026")

        assert result == "2026-01-22T10:00:00"

    def test_returns_empty_string_for_invalid_format(self):
        """Should return empty string for unparseable time."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        result = crawler._parse_post_time("invalid time")

        assert result == ""


class TestParsePushTime:
    """Tests for comment/push time parsing."""

    def test_extracts_time_from_ip_datetime_string(self):
        """Should extract MM/DD HH:MM from ' 1.2.3.4 01/22 10:30'."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        result = crawler._parse_push_time(" 1.2.3.4 01/22 10:30")

        assert result == "01/22 10:30"

    def test_extracts_time_without_ip(self):
        """Should extract MM/DD HH:MM from '01/22 10:30'."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        result = crawler._parse_push_time("01/22 10:30")

        assert result == "01/22 10:30"

    def test_returns_none_for_missing_time(self):
        """Should return None when no time pattern found."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        result = crawler._parse_push_time("")

        assert result is None


class TestParseArticle:
    """Tests for article parsing from HTML."""

    @pytest.fixture
    def sample_article_html(self):
        """Minimal PTT article HTML structure."""
        return """
        <html>
        <head><meta charset="utf-8"></head>
        <body>
        <div id="main-content" class="bbs-screen bbs-content">
            <div class="article-metaline">
                <span class="article-meta-tag">作者</span>
                <span class="article-meta-value">testuser (Test User)</span>
            </div>
            <div class="article-metaline">
                <span class="article-meta-tag">看板</span>
                <span class="article-meta-value">C_Chat</span>
            </div>
            <div class="article-metaline">
                <span class="article-meta-tag">標題</span>
                <span class="article-meta-value">[閒聊] 測試文章</span>
            </div>
            <div class="article-metaline">
                <span class="article-meta-tag">時間</span>
                <span class="article-meta-value">Wed Jan 22 10:00:00 2026</span>
            </div>

            這是文章內容。
            第二行內容。

            --
            ※ 發信站: 批踢踢實業坊(ptt.cc)

            <div class="push">
                <span class="push-tag">推 </span>
                <span class="push-userid">user1</span>
                <span class="push-content">: 推推</span>
                <span class="push-ipdatetime"> 1.2.3.4 01/22 10:05</span>
            </div>
            <div class="push">
                <span class="push-tag">噓 </span>
                <span class="push-userid">user2</span>
                <span class="push-content">: 噓一下</span>
                <span class="push-ipdatetime"> 5.6.7.8 01/22 10:10</span>
            </div>
            <div class="push">
                <span class="push-tag">→ </span>
                <span class="push-userid">user3</span>
                <span class="push-content">: 路過</span>
                <span class="push-ipdatetime"> 9.10.11.12 01/22 10:15</span>
            </div>
        </div>
        </body>
        </html>
        """

    def test_extracts_author_username_only(self, sample_article_html):
        """Should extract 'testuser' from 'testuser (Test User)'."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(sample_article_html, "lxml")

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert article.author == "testuser"

    def test_extracts_title(self, sample_article_html):
        """Should extract title from metaline."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(sample_article_html, "lxml")

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert article.title == "[閒聊] 測試文章"

    def test_extracts_post_time_as_iso(self, sample_article_html):
        """Should parse post time to ISO format."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(sample_article_html, "lxml")

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert article.post_time == "2026-01-22T10:00:00"

    def test_counts_push_boo_neutral(self, sample_article_html):
        """Should count push/boo/neutral comments correctly."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(sample_article_html, "lxml")

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert article.push_count == 1
            assert article.boo_count == 1
            assert article.neutral_count == 1

    def test_extracts_comment_with_timestamp(self, sample_article_html):
        """Should extract comments with their timestamps."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(sample_article_html, "lxml")

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert len(article.comments) == 3
            assert article.comments[0]["user"] == "user1"
            assert article.comments[0]["time"] == "01/22 10:05"
            assert article.comments[0]["type"] == "推"

    def test_extracts_article_id_from_url(self, sample_article_html):
        """Should extract article ID from URL."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(sample_article_html, "lxml")

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert article.article_id == "M.1234567890.A.ABC"

    def test_extracts_board_from_url(self, sample_article_html):
        """Should extract board name from URL."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(sample_article_html, "lxml")

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert article.board == "C_Chat"

    def test_returns_none_when_fetch_fails(self):
        """Should return None if page cannot be fetched."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            mock_fetch.return_value = None

            article = crawler.parse_article("https://www.ptt.cc/bbs/C_Chat/M.1234567890.A.ABC.html")

            assert article is None


class TestSearchViralPosts:
    """Tests for searching viral posts by recommend count."""

    @pytest.fixture
    def search_results_html(self):
        """PTT search results page HTML."""
        return """
        <html>
        <body>
        <div class="r-list-container">
            <div class="r-ent">
                <div class="title">
                    <a href="/bbs/C_Chat/M.1111111111.A.AAA.html">[閒聊] 熱門文章1</a>
                </div>
            </div>
            <div class="r-ent">
                <div class="title">
                    <a href="/bbs/C_Chat/M.2222222222.A.BBB.html">[閒聊] 熱門文章2</a>
                </div>
            </div>
            <div class="r-ent">
                <div class="title">
                    (本文已被刪除) [author]
                </div>
            </div>
        </div>
        </body>
        </html>
        """

    def test_returns_article_urls_from_search(self, search_results_html):
        """Should return list of article URLs from search results."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(search_results_html, "lxml")

            urls = crawler.search_viral_posts("C_Chat", min_recommend=50, pages=1)

            assert len(urls) == 2
            assert "https://www.ptt.cc/bbs/C_Chat/M.1111111111.A.AAA.html" in urls
            assert "https://www.ptt.cc/bbs/C_Chat/M.2222222222.A.BBB.html" in urls


class TestGetRecentPosts:
    """Tests for getting recent posts from a board."""

    @pytest.fixture
    def board_index_html(self):
        """PTT board index page HTML."""
        return """
        <html>
        <body>
        <div class="btn-group-paging">
            <a class="btn wide" href="/bbs/C_Chat/index1.html">最舊</a>
            <a class="btn wide" href="/bbs/C_Chat/index99.html">‹ 上頁</a>
            <a class="btn wide" href="/bbs/C_Chat/index.html">最新</a>
        </div>
        <div class="r-list-container">
            <div class="r-ent">
                <div class="title">
                    <a href="/bbs/C_Chat/M.3333333333.A.CCC.html">[閒聊] 最新文章</a>
                </div>
            </div>
        </div>
        </body>
        </html>
        """

    def test_returns_recent_article_urls(self, board_index_html):
        """Should return list of recent article URLs."""
        from ptt_crawler import PTTCrawler

        crawler = PTTCrawler()
        with patch.object(crawler, '_fetch') as mock_fetch:
            from bs4 import BeautifulSoup
            mock_fetch.return_value = BeautifulSoup(board_index_html, "lxml")

            urls = crawler.get_recent_posts("C_Chat", pages=1)

            assert len(urls) >= 1
            assert "https://www.ptt.cc/bbs/C_Chat/M.3333333333.A.CCC.html" in urls


class TestAntiBlockingMeasures:
    """Tests for anti-blocking behavior."""

    def test_delay_is_applied_between_requests(self):
        """Crawler should delay between requests."""
        from ptt_crawler import PTTCrawler
        import time

        crawler = PTTCrawler(delay_range=(0.1, 0.2))

        start = time.time()
        with patch('requests.Session.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text="<html></html>",
                raise_for_status=Mock()
            )
            crawler._fetch("https://example.com")
            crawler._fetch("https://example.com")

        elapsed = time.time() - start
        # Should have at least one delay (0.1s minimum)
        assert elapsed >= 0.1

    def test_retries_on_failure_with_backoff(self):
        """Should retry failed requests with exponential backoff."""
        from ptt_crawler import PTTCrawler
        import requests

        crawler = PTTCrawler(delay_range=(0.01, 0.02))  # Minimal delay for test

        with patch.object(crawler.session, 'get') as mock_get:
            mock_get.side_effect = requests.RequestException("Connection error")

            result = crawler._fetch("https://example.com", max_retries=2)

            assert result is None
            assert mock_get.call_count == 2


class TestCollectDataset:
    """Tests for dataset collection function."""

    def test_collect_dataset_saves_json_file(self, tmp_path):
        """Should save collected articles to JSON file."""
        from ptt_crawler import PTTCrawler, collect_dataset
        from dataclasses import asdict

        with patch.object(PTTCrawler, 'search_viral_posts') as mock_search, \
             patch.object(PTTCrawler, 'get_recent_posts') as mock_recent, \
             patch.object(PTTCrawler, 'parse_article') as mock_parse:

            # Return empty results for simplicity
            mock_search.return_value = []
            mock_recent.return_value = []

            collect_dataset(
                boards=["TestBoard"],
                viral_pages=1,
                recent_pages=1,
                output_dir=str(tmp_path)
            )

            # Should create a JSON file
            json_files = list(tmp_path.glob("ptt_articles_*.json"))
            assert len(json_files) == 1

    def test_collect_dataset_includes_viral_label(self, tmp_path):
        """Should mark articles as viral based on push/boo counts."""
        from ptt_crawler import PTTCrawler, Article, collect_dataset
        import json

        viral_article = Article(
            article_id="M.1234",
            board="Test",
            title="Viral Post",
            author="user1",
            post_time="2026-01-22T10:00:00",
            content="content",
            comments=[],
            push_count=120,
            boo_count=10,
            neutral_count=5,
            url="https://example.com/1"
        )

        non_viral_article = Article(
            article_id="M.5678",
            board="Test",
            title="Normal Post",
            author="user2",
            post_time="2026-01-22T11:00:00",
            content="content",
            comments=[],
            push_count=20,
            boo_count=5,
            neutral_count=3,
            url="https://example.com/2"
        )

        with patch.object(PTTCrawler, 'search_viral_posts') as mock_search, \
             patch.object(PTTCrawler, 'get_recent_posts') as mock_recent, \
             patch.object(PTTCrawler, 'parse_article') as mock_parse:

            mock_search.return_value = ["https://example.com/1"]
            mock_recent.return_value = ["https://example.com/2"]
            mock_parse.side_effect = [viral_article, non_viral_article]

            collect_dataset(
                boards=["TestBoard"],
                viral_pages=1,
                recent_pages=1,
                output_dir=str(tmp_path),
                max_viral_per_board=1,
                max_nonviral_per_board=1
            )

            # Read and verify
            json_files = list(tmp_path.glob("ptt_articles_*.json"))
            with open(json_files[0], "r", encoding="utf-8") as f:
                articles = json.load(f)

            assert len(articles) == 2

            viral = next(a for a in articles if a["article_id"] == "M.1234")
            non_viral = next(a for a in articles if a["article_id"] == "M.5678")

            # Viral: push >= 100 AND (push - boo) >= 100
            assert viral["is_viral"] == True  # 120 >= 100 and 120-10=110 >= 100
            assert non_viral["is_viral"] == False  # 20 < 100
