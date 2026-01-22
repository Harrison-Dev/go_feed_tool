#!/usr/bin/env python3
"""
統計現有 PTT 資料集的文章數量和重複情況。

Usage:
    python data_stats.py                    # 統計所有資料檔
    python data_stats.py --merge            # 合併並去重
    python data_stats.py --output merged.json  # 指定輸出檔名
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def load_all_datasets(data_dir: Path) -> list[tuple[str, list[dict]]]:
    """載入指定目錄下所有 JSON 資料集。"""
    datasets = []
    for json_file in sorted(data_dir.glob("ptt_articles_*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            datasets.append((json_file.name, data))
    return datasets


def get_article_ids(articles: list[dict]) -> set[str]:
    """取得所有文章 ID。"""
    return {a.get("article_id", "") for a in articles if a.get("article_id")}


def print_stats(datasets: list[tuple[str, list[dict]]]):
    """印出各資料集統計。"""
    all_ids = set()
    total_articles = 0
    total_viral = 0
    total_nonviral = 0

    print("=" * 70)
    print("PTT 資料集統計")
    print("=" * 70)
    print(f"{'檔案名稱':<45} {'總數':>6} {'爆文':>6} {'一般':>6}")
    print("-" * 70)

    for filename, articles in datasets:
        viral = sum(1 for a in articles if a.get("is_viral"))
        nonviral = len(articles) - viral
        ids = get_article_ids(articles)

        print(f"{filename:<45} {len(articles):>6} {viral:>6} {nonviral:>6}")

        total_articles += len(articles)
        total_viral += viral
        total_nonviral += nonviral
        all_ids.update(ids)

    print("-" * 70)
    print(f"{'總計 (含重複)':<45} {total_articles:>6} {total_viral:>6} {total_nonviral:>6}")
    print(f"{'不重複文章 ID 數':<45} {len(all_ids):>6}")
    print("=" * 70)

    return all_ids


def merge_datasets(datasets: list[tuple[str, list[dict]]]) -> list[dict]:
    """合併並去重所有資料集，保留最新版本。"""
    article_map = {}  # article_id -> article

    for filename, articles in datasets:
        for article in articles:
            article_id = article.get("article_id", "")
            if article_id:
                # 保留較新的版本（有更多留言的）
                existing = article_map.get(article_id)
                if not existing or len(article.get("comments", [])) > len(existing.get("comments", [])):
                    article_map[article_id] = article

    return list(article_map.values())


def main():
    parser = argparse.ArgumentParser(description="PTT 資料集統計工具")
    parser.add_argument("--data-dir", default="../data", help="資料目錄 (預設: ../data)")
    parser.add_argument("--merge", action="store_true", help="合併並去重所有資料集")
    parser.add_argument("--output", default="ptt_articles_merged.json", help="合併後輸出檔名")

    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data"
    if args.data_dir != "../data":
        data_dir = Path(args.data_dir)

    if not data_dir.exists():
        print(f"Error: 資料目錄不存在: {data_dir}")
        return

    datasets = load_all_datasets(data_dir)
    if not datasets:
        print(f"Error: 找不到資料檔 (ptt_articles_*.json) 在 {data_dir}")
        return

    all_ids = print_stats(datasets)

    if args.merge:
        print(f"\n正在合併 {len(datasets)} 個資料集...")
        merged = merge_datasets(datasets)

        viral = sum(1 for a in merged if a.get("is_viral"))
        nonviral = len(merged) - viral

        output_path = data_dir / args.output
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        print(f"\n合併完成!")
        print(f"  輸出檔案: {output_path}")
        print(f"  不重複文章: {len(merged)} 篇")
        print(f"  爆文: {viral} / 一般: {nonviral}")


if __name__ == "__main__":
    main()
