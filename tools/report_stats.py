"""Print a Markdown table of posts / comments / low-value comments per batch."""
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from digest_for_analysis import is_low_value

PLATFORM_NAMES = {"xhs": "小红书", "zhihu": "知乎"}


def read_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                yield json.loads(line)


def find_batches(root: Path) -> list[Path]:
    if (root / "posts.jsonl").exists():
        return [root]
    return sorted(
        child for child in root.iterdir()
        if child.is_dir() and (child / "posts.jsonl").exists()
    )


def count_batch(batch: Path) -> list[dict]:
    posts = Counter(p.get("platform", "") for p in read_jsonl(batch / "posts.jsonl"))
    comments = Counter()
    low = Counter()
    for comment in read_jsonl(batch / "comments.jsonl"):
        platform = comment.get("platform", "")
        comments[platform] += 1
        if is_low_value(comment.get("content", "")):
            low[platform] += 1
    platforms = sorted(set(posts) | set(comments))
    return [
        {
            "platform": platform,
            "batch": batch.name,
            "posts": posts[platform],
            "comments": comments[platform],
            "low": low[platform],
        }
        for platform in platforms
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="批次目录，或其父目录")
    args = parser.parse_args()

    batches: list[Path] = []
    for raw in args.roots:
        root = Path(raw)
        if not root.is_dir():
            parser.error(f"目录不存在：{root}")
        batches.extend(find_batches(root))

    rows = [row for batch in batches for row in count_batch(batch)]
    print("| 平台 | 批次 | 帖子 | 评论 | 低价值评论 | 占比 |")
    print("|---|---|---:|---:|---:|---:|")
    total_posts = total_comments = total_low = 0
    for row in rows:
        rate = f"{row['low'] / row['comments'] * 100:.0f}%" if row["comments"] else "—"
        name = PLATFORM_NAMES.get(row["platform"], row["platform"] or "—")
        print(f"| {name} | {row['batch']} | {row['posts']} | {row['comments']} | {row['low']} | {rate} |")
        total_posts += row["posts"]
        total_comments += row["comments"]
        total_low += row["low"]
    if rows:
        rate = f"{total_low / total_comments * 100:.0f}%" if total_comments else "—"
        print(f"| **合计** | — | **{total_posts}** | **{total_comments}** | **{total_low}** | **{rate}** |")


if __name__ == "__main__":
    main()
