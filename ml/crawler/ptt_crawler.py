"""
PTT Crawler for Viral Post Prediction Dataset

Collects articles from PTT boards with comment timestamps for feature engineering.
"""

import json
import random
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


@dataclass
class Comment:
    """Represents a single comment/push on a PTT article."""
    type: str  # 推, 噓, →
    user: str
    content: str
    time: Optional[str]  # MM/DD HH:MM format or None


@dataclass
class Article:
    """Represents a PTT article with all metadata."""
    article_id: str
    board: str
    title: str
    author: str
    post_time: str  # ISO format
    content: str
    comments: list[dict]
    push_count: int
    boo_count: int
    neutral_count: int
    url: str


class PTTCrawler:
    """PTT Crawler with anti-blocking measures."""

    BASE_URL = "https://www.ptt.cc"

    def __init__(self, delay_range: tuple[float, float] = (1.0, 3.0)):
        self.session = requests.Session()
        self.delay_range = delay_range

        # Set browser-like headers
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        })

        # Set age verification cookie
        self.session.cookies.set("over18", "1", domain=".ptt.cc")

    def _delay(self):
        """Random delay between requests."""
        time.sleep(random.uniform(*self.delay_range))

    def _fetch(self, url: str, max_retries: int = 3) -> Optional[BeautifulSoup]:
        """Fetch URL with retry logic."""
        for attempt in range(max_retries):
            try:
                self._delay()
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return BeautifulSoup(response.text, "lxml")
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.random()
                    time.sleep(wait_time)
                else:
                    return None
        return None

    def _parse_post_time(self, time_str: str) -> str:
        """Parse PTT post time format to ISO format."""
        try:
            dt = datetime.strptime(time_str, "%a %b %d %H:%M:%S %Y")
            return dt.isoformat()
        except ValueError:
            return ""

    def _parse_push_time(self, time_str: str) -> Optional[str]:
        """Parse PTT push time format. Returns MM/DD HH:MM or None."""
        match = re.search(r"(\d{2}/\d{2} \d{2}:\d{2})", time_str)
        if match:
            return match.group(1)
        return None

    def parse_article(self, url: str) -> Optional[Article]:
        """Parse a single PTT article."""
        soup = self._fetch(url)
        if not soup:
            return None

        try:
            # Extract article ID from URL
            match = re.search(r"/([^/]+)\.html$", url)
            article_id = match.group(1) if match else url

            # Extract board from URL
            board_match = re.search(r"/bbs/([^/]+)/", url)
            board = board_match.group(1) if board_match else "unknown"

            # Extract metadata
            metalines = soup.select("div.article-metaline")
            author = ""
            title = ""
            post_time_str = ""

            for metaline in metalines:
                tag = metaline.select_one("span.article-meta-tag")
                value = metaline.select_one("span.article-meta-value")
                if tag and value:
                    tag_text = tag.get_text(strip=True)
                    value_text = value.get_text(strip=True)
                    if tag_text == "作者":
                        author = value_text.split(" ")[0]
                    elif tag_text == "標題":
                        title = value_text
                    elif tag_text == "時間":
                        post_time_str = value_text

            post_time = self._parse_post_time(post_time_str)

            # Extract content
            main_content = soup.select_one("div#main-content")
            content = self._extract_content(main_content) if main_content else ""

            # Extract comments
            comments = []
            push_count = 0
            boo_count = 0
            neutral_count = 0

            for push in soup.select("div.push"):
                push_tag = push.select_one("span.push-tag")
                push_user = push.select_one("span.push-userid")
                push_content = push.select_one("span.push-content")
                push_time = push.select_one("span.push-ipdatetime")

                if push_tag and push_user and push_content:
                    tag_text = push_tag.get_text(strip=True)

                    comment = Comment(
                        type=tag_text,
                        user=push_user.get_text(strip=True),
                        content=push_content.get_text(strip=True).lstrip(": "),
                        time=self._parse_push_time(push_time.get_text(strip=True) if push_time else "")
                    )
                    comments.append(asdict(comment))

                    if tag_text == "推":
                        push_count += 1
                    elif tag_text == "噓":
                        boo_count += 1
                    else:
                        neutral_count += 1

            return Article(
                article_id=article_id,
                board=board,
                title=title,
                author=author,
                post_time=post_time,
                content=content,
                comments=comments,
                push_count=push_count,
                boo_count=boo_count,
                neutral_count=neutral_count,
                url=url
            )
        except Exception:
            return None

    def _extract_content(self, main_content) -> str:
        """Extract article content, excluding metadata and pushes."""
        content_text = main_content.get_text()
        markers = ["--", "※ 發信站: 批踢踢實業坊"]
        for marker in markers:
            if marker in content_text:
                content_text = content_text.split(marker)[0]
        return content_text.strip()

    def search_viral_posts(self, board: str, min_recommend: int = 50, pages: int = 5) -> list[str]:
        """Search for viral posts using PTT's recommend search."""
        article_urls = []
        search_url = f"{self.BASE_URL}/bbs/{board}/search?q=recommend:{min_recommend}"

        for page in range(1, pages + 1):
            page_url = f"{search_url}&page={page}" if page > 1 else search_url
            soup = self._fetch(page_url)

            if not soup:
                continue

            for entry in soup.select("div.r-ent"):
                title_elem = entry.select_one("div.title a")
                if title_elem and title_elem.get("href"):
                    article_url = urljoin(self.BASE_URL, title_elem["href"])
                    article_urls.append(article_url)

        return article_urls

    def get_recent_posts(self, board: str, pages: int = 10) -> list[str]:
        """Get recent posts from a board."""
        article_urls = []
        board_url = f"{self.BASE_URL}/bbs/{board}/index.html"
        soup = self._fetch(board_url)

        if not soup:
            return article_urls

        # Find latest page number
        paging = soup.select_one("div.btn-group-paging a.btn.wide:nth-child(2)")
        if paging and paging.get("href"):
            match = re.search(r"index(\d+)\.html", paging["href"])
            latest_page = int(match.group(1)) + 1 if match else 1
        else:
            latest_page = 1

        # Crawl pages
        for i in range(pages):
            page_num = latest_page - i
            if page_num < 1:
                break

            if i == 0:
                # Reuse already fetched soup for first page
                page_soup = soup
            else:
                page_url = f"{self.BASE_URL}/bbs/{board}/index{page_num}.html"
                page_soup = self._fetch(page_url)

            if not page_soup:
                continue

            for entry in page_soup.select("div.r-ent"):
                title_elem = entry.select_one("div.title a")
                if title_elem and title_elem.get("href"):
                    if "(本文已被刪除)" not in (title_elem.text or ""):
                        article_url = urljoin(self.BASE_URL, title_elem["href"])
                        article_urls.append(article_url)

        return article_urls


def is_viral(article: Article) -> bool:
    """Determine if an article is viral based on push/boo counts."""
    return article.push_count >= 100 and (article.push_count - article.boo_count) >= 100


def collect_dataset(
    boards: list[str],
    viral_pages: int = 3,
    recent_pages: int = 10,
    output_dir: str = "data",
    max_viral_per_board: int = 200,
    max_nonviral_per_board: int = 200
) -> list[dict]:
    """
    Collect dataset for viral post prediction.

    Args:
        boards: List of board names to crawl
        viral_pages: Pages to crawl per recommend level
        recent_pages: Pages to crawl for recent (non-viral) posts
        output_dir: Directory to save data
        max_viral_per_board: Max viral articles per board
        max_nonviral_per_board: Max non-viral articles per board

    Returns:
        List of article dictionaries with is_viral label
    """
    crawler = PTTCrawler()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_articles = []

    for board in boards:
        # Collect viral post URLs
        viral_urls = set()
        for recommend in [50, 60, 70, 80, 90, 100]:
            urls = crawler.search_viral_posts(board, recommend, pages=viral_pages)
            viral_urls.update(urls)

        # Collect recent post URLs
        recent_urls = set(crawler.get_recent_posts(board, pages=recent_pages))
        non_viral_urls = recent_urls - viral_urls

        # Parse viral articles
        viral_list = list(viral_urls)[:max_viral_per_board]
        for url in viral_list:
            article = crawler.parse_article(url)
            if article:
                article_dict = asdict(article)
                article_dict["is_viral"] = is_viral(article)
                all_articles.append(article_dict)

        # Parse non-viral articles
        non_viral_list = list(non_viral_urls)[:max_nonviral_per_board]
        for url in non_viral_list:
            article = crawler.parse_article(url)
            if article:
                article_dict = asdict(article)
                article_dict["is_viral"] = is_viral(article)
                all_articles.append(article_dict)

    # Save to JSON
    output_file = output_path / f"ptt_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    return all_articles
