"""Build a relevance-ranked, noise-filtered digest from batch50 output dirs."""
import argparse
import json
import re
from pathlib import Path

VALUE_WORDS = [
    "面经", "面试", "一面", "二面", "三面", "终面", "hr面", "笔试", "手撕", "代码题",
    "公司", "岗位", "简历", "项目", "实习", "秋招", "校招", "offer", "包", "薪资",
    "vla", "wam", "世界模型", "world model", "灵巧手", "dexterous", "具身",
    "pi0", "pi 0", "pi0.5", "π0", "so101", "so-101", "rltoken", "rl token",
    "强化学习", "模仿学习", "diffusion policy", "flow matching", "动作专家",
    "数据集", "训练", "微调", "真机", "仿真", "评测", "部署", "模型", "算法",
    "transformer", "vlm", "llm", "token", "critic", "actor", "ppo", "grpo", "dagger",
]

LOW_VALUE_PATTERNS = [
    r"^\[[^\]]{1,8}\]$", r"^[+\-0-9\s。.!！?？~～]+$", r"^(蹲|mark|码|顶|打卡|接好运|谢谢|感谢|好的|收到|牛|强|太强了|厉害了|恭喜|加油|同问|求|\+1)[\s!！。.~～]*$",
    r"^(哈哈哈+|笑死|绷不住|哭了|羡慕|同款|一样)+[\s!！。.~～]*$",
]

INTERVIEW_HINTS = [
    "面经", "面试", "秋招", "校招", "实习", "offer", "简历", "求职", "招聘", "内推",
    "公司", "岗位", "算法", "具身", "vla", "世界模型", "灵巧手", "机器人",
]


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def is_low_value(text):
    t = norm(text)
    if len(t) < 12:
        return True
    if any(re.match(p, t, flags=re.I) for p in LOW_VALUE_PATTERNS):
        return True
    # emoji-only / punctuation-heavy
    core = re.sub(r"\[[^\]]{1,12}\]", "", t)
    core = re.sub(r"[^\w一-鿿]+", "", core)
    return len(core) < 8


def comment_score(text):
    t = norm(text).lower()
    return sum(1 for w in VALUE_WORDS if w in t)


def post_score(title, body):
    t = (title + " " + body).lower()
    score = 0
    score += 3 * sum(1 for w in ("vla", "wam", "世界模型", "world model", "灵巧手", "dexterous", "pi0", "pi0.5", "so101", "rltoken", "rl token") if w in t)
    score += 1 * sum(1 for w in ("具身", "机器人", "面经", "面试", "算法", "实习", "秋招", "校招", "offer") if w in t)
    return score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--min-score", type=int, default=2)
    ap.add_argument("--min-comment-score", type=int, default=1)
    ap.add_argument("--include-low-comments", action="store_true")
    args = ap.parse_args()

    posts, comments = {}, {}
    order = []
    for d in args.dirs:
        d = Path(d)
        for line in (d / "posts.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            p = json.loads(line)
            key = (p["platform"], str(p["post_id"]))
            if key not in posts:
                posts[key] = p
                order.append(key)
        for line in (d / "comments.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            comments.setdefault((c["platform"], str(c["post_id"])), []).append(c)

    rows = []
    for key in order:
        p = posts[key]
        s = post_score(p.get("title", ""), p.get("body", ""))
        rows.append((s, p))
    rows.sort(key=lambda x: -x[0])

    shown = 0
    for s, p in rows:
        if s < args.min_score:
            continue
        shown += 1
        key = (p["platform"], str(p["post_id"]))
        note = " [正文很短，可能以图片为主]" if len(p.get("body") or "") < 120 else ""
        print(f"\n===== [{s}] {p.get('title','')}{note}")
        print(f"URL: {p.get('url','')}")
        print(f"platform={p['platform']} post_id={p['post_id']} keyword={p.get('source_keyword','')} comments={p.get('comment_count_reported','')}")
        print("BODY:")
        print(norm(p.get("body", "")))
        kept = []
        for c in comments.get(key, []):
            if not args.include_low_comments and is_low_value(c.get("content", "")):
                continue
            cs = comment_score(c.get("content", ""))
            if cs < args.min_comment_score:
                continue
            kept.append((cs, c))
        kept.sort(key=lambda x: -x[0])
        if kept:
            print("COMMENTS:")
            for cs, c in kept:
                print(f"  ({cs}) cid={c.get('comment_id')} parent={c.get('parent_comment_id') or '-'}: {norm(c.get('content',''))}")
    print(f"\n\n### posts shown {shown} / {len(rows)}")


if __name__ == "__main__":
    main()
