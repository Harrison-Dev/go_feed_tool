#!/usr/bin/env python3
"""
CLI script for collecting PTT dataset.

Usage:
    python collect_data.py                    # Default: C_Chat, Stock boards
    python collect_data.py --boards Gossiping C_Chat Stock
    python collect_data.py --test             # Quick test run
"""

import argparse
from pathlib import Path

from ptt_crawler import collect_dataset


def main():
    parser = argparse.ArgumentParser(
        description="Collect PTT articles for viral post prediction"
    )
    parser.add_argument(
        "--boards",
        nargs="+",
        default=["C_Chat", "Stock"],
        help="Board names to crawl (default: C_Chat Stock)"
    )
    parser.add_argument(
        "--viral-pages",
        type=int,
        default=3,
        help="Pages to crawl per recommend level (default: 3)"
    )
    parser.add_argument(
        "--recent-pages",
        type=int,
        default=10,
        help="Pages to crawl for recent posts (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data",
        help="Output directory (default: data)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Quick test run with minimal data"
    )

    args = parser.parse_args()

    if args.test:
        print("Running in TEST mode (minimal data)")
        args.viral_pages = 1
        args.recent_pages = 2
        max_viral = 5
        max_nonviral = 5
    else:
        max_viral = 200
        max_nonviral = 200

    output_path = Path(__file__).parent / args.output

    print(f"Configuration:")
    print(f"  Boards: {args.boards}")
    print(f"  Viral pages per level: {args.viral_pages}")
    print(f"  Recent pages: {args.recent_pages}")
    print(f"  Output: {output_path}")
    print()

    articles = collect_dataset(
        boards=args.boards,
        viral_pages=args.viral_pages,
        recent_pages=args.recent_pages,
        output_dir=str(output_path),
        max_viral_per_board=max_viral,
        max_nonviral_per_board=max_nonviral
    )

    print(f"\nCollected {len(articles)} articles")
    viral_count = sum(1 for a in articles if a.get("is_viral"))
    print(f"  Viral: {viral_count}")
    print(f"  Non-viral: {len(articles) - viral_count}")


if __name__ == "__main__":
    main()
