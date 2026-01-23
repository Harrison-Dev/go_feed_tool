#!/usr/bin/env python3
"""
增量爬蟲腳本：擴充 PTT 資料集至指定數量。

避免重複抓取已有的文章，並支援中斷後繼續。

Usage:
    python incremental_crawl.py --target 1000    # 爬到 1000 篇
    python incremental_crawl.py --target 1000 --boards Gossiping Stock  # 指定看板
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.ptt_crawler import PTTCrawler, is_viral
from dataclasses import asdict


def load_existing_ids(data_dir: Path) -> set[str]:
    """載入所有已存在的文章 ID。"""
    existing_ids = set()
    for json_file in data_dir.glob("ptt_articles_*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for article in data:
                    article_id = article.get("article_id", "")
                    if article_id:
                        existing_ids.add(article_id)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: 無法讀取 {json_file}: {e}")
    return existing_ids


def count_unique_articles(data_dir: Path) -> int:
    """計算不重複文章總數。"""
    return len(load_existing_ids(data_dir))


def save_articles(articles: list[dict], output_path: Path):
    """儲存文章到 JSON 檔案。"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def incremental_crawl(
    target: int,
    boards: list[str],
    data_dir: Path,
    batch_size: int = 50,
    delay_range: tuple[float, float] = (2.0, 4.0),
) -> int:
    """
    增量爬取文章直到達到目標數量。

    Args:
        target: 目標文章總數
        boards: 要爬取的看板列表
        data_dir: 資料儲存目錄
        batch_size: 每批次儲存的文章數
        delay_range: 請求間隔範圍（秒）

    Returns:
        實際爬取的新文章數
    """
    existing_ids = load_existing_ids(data_dir)
    current_count = len(existing_ids)

    print(f"目前已有 {current_count} 篇不重複文章")
    print(f"目標: {target} 篇")

    if current_count >= target:
        print("已達到目標數量，無需爬取")
        return 0

    needed = target - current_count
    print(f"需要再爬取約 {needed} 篇新文章")
    print(f"看板: {', '.join(boards)}")
    print("-" * 50)

    crawler = PTTCrawler(delay_range=delay_range)
    new_articles = []
    total_crawled = 0
    skipped_duplicate = 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = data_dir / f"ptt_articles_{timestamp}.json"

    try:
        for board in boards:
            if len(new_articles) >= needed:
                break

            print(f"\n[{board}] 開始爬取...")

            # 1. 爬取爆文（高推文數）
            print(f"  搜尋爆文...")
            for recommend in [50, 60, 70, 80, 90, 100]:
                if len(new_articles) >= needed:
                    break

                urls = crawler.search_viral_posts(board, recommend, pages=3)
                for url in urls:
                    if len(new_articles) >= needed:
                        break

                    # 從 URL 取得 article_id 來檢查是否已存在
                    article_id = url.split("/")[-1].replace(".html", "")
                    if article_id in existing_ids:
                        skipped_duplicate += 1
                        continue

                    article = crawler.parse_article(url)
                    if article:
                        article_dict = asdict(article)
                        article_dict["is_viral"] = is_viral(article)
                        new_articles.append(article_dict)
                        existing_ids.add(article.article_id)
                        total_crawled += 1

                        # 進度顯示
                        if total_crawled % 10 == 0:
                            print(f"    已爬取 {total_crawled} 篇新文章 (跳過 {skipped_duplicate} 篇重複)")

                        # 批次儲存
                        if len(new_articles) % batch_size == 0:
                            save_articles(new_articles, output_file)
                            print(f"    [儲存] {len(new_articles)} 篇")

            # 2. 爬取一般文章（最近的文章）
            print(f"  搜尋一般文章...")
            recent_urls = crawler.get_recent_posts(board, pages=20)
            for url in recent_urls:
                if len(new_articles) >= needed:
                    break

                article_id = url.split("/")[-1].replace(".html", "")
                if article_id in existing_ids:
                    skipped_duplicate += 1
                    continue

                article = crawler.parse_article(url)
                if article:
                    article_dict = asdict(article)
                    article_dict["is_viral"] = is_viral(article)
                    new_articles.append(article_dict)
                    existing_ids.add(article.article_id)
                    total_crawled += 1

                    if total_crawled % 10 == 0:
                        print(f"    已爬取 {total_crawled} 篇新文章 (跳過 {skipped_duplicate} 篇重複)")

                    if len(new_articles) % batch_size == 0:
                        save_articles(new_articles, output_file)
                        print(f"    [儲存] {len(new_articles)} 篇")

    except KeyboardInterrupt:
        print("\n\n[中斷] 正在儲存已爬取的文章...")

    # 最終儲存
    if new_articles:
        save_articles(new_articles, output_file)
        viral = sum(1 for a in new_articles if a.get("is_viral"))
        nonviral = len(new_articles) - viral

        print("\n" + "=" * 50)
        print(f"爬取完成!")
        print(f"  新增文章: {len(new_articles)} 篇")
        print(f"  爆文: {viral} / 一般: {nonviral}")
        print(f"  跳過重複: {skipped_duplicate} 篇")
        print(f"  輸出檔案: {output_file}")
        print(f"  目前總數: {count_unique_articles(data_dir)} 篇")
    else:
        print("\n沒有新文章可爬取")

    return len(new_articles)


def main():
    parser = argparse.ArgumentParser(description="PTT 增量爬蟲")
    parser.add_argument("--target", type=int, default=1000, help="目標文章總數 (預設: 1000)")
    parser.add_argument("--boards", nargs="+", default=["Gossiping", "Stock", "NBA", "LoL"],
                        help="要爬取的看板 (預設: Gossiping Stock NBA LoL)")
    parser.add_argument("--batch-size", type=int, default=50, help="批次儲存大小 (預設: 50)")
    parser.add_argument("--delay-min", type=float, default=2.0, help="最小延遲秒數 (預設: 2.0)")
    parser.add_argument("--delay-max", type=float, default=4.0, help="最大延遲秒數 (預設: 4.0)")

    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    incremental_crawl(
        target=args.target,
        boards=args.boards,
        data_dir=data_dir,
        batch_size=args.batch_size,
        delay_range=(args.delay_min, args.delay_max),
    )


if __name__ == "__main__":
    main()
