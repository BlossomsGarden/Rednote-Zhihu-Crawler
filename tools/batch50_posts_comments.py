"""Collect one batch of at most 50 XHS or Zhihu posts and all accessible comments."""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from media_platform.xhs.core import XiaoHongShuCrawler
from media_platform.xhs.field import SearchSortType
from media_platform.xhs.help import get_search_id
from media_platform.zhihu.core import ZhihuCrawler
from parsel import Selector
from playwright.async_api import async_playwright


def append(path, records):
    with path.open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


async def comments_xhs(client, post_id, token, delay):
    rows, seen = [], set()

    def add(items, root=""):
        for item in items:
            cid = item.get("id")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            rows.append({"platform": "xhs", "post_id": post_id, "comment_id": cid,
                         "parent_comment_id": (item.get("target_comment") or {}).get("id") or root,
                         "content": item.get("content", ""), "created_at": item.get("create_time")})

    cursor = ""
    while True:
        page = await client.get_note_comments(post_id, token, cursor)
        if not isinstance(page, dict) or "comments" not in page:
            raise RuntimeError(f"评论响应缺失: {post_id}")
        for root in page["comments"]:
            add([root])
            root_id = root.get("id", "")
            add(root.get("sub_comments") or [], root_id)
            child_cursor = root.get("sub_comment_cursor") or ""
            has_more = root.get("sub_comment_has_more", False)
            while has_more:
                await asyncio.sleep(delay)
                child = await client.get_note_sub_comments(post_id, root_id, token, cursor=child_cursor)
                if not isinstance(child, dict) or "comments" not in child:
                    raise RuntimeError(f"回复响应缺失: {post_id}/{root_id}")
                add(child["comments"], root_id)
                has_more = child.get("has_more", False)
                next_cursor = child.get("cursor") or ""
                if has_more and (not next_cursor or next_cursor == child_cursor):
                    raise RuntimeError(f"回复分页停滞: {post_id}/{root_id}")
                child_cursor = next_cursor
        if not page.get("has_more", False):
            return rows
        next_cursor = page.get("cursor") or ""
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError(f"评论分页停滞: {post_id}")
        cursor = next_cursor
        await asyncio.sleep(delay)


async def comments_zhihu(client, detail, delay):
    rows, seen = [], set()

    def add(data):
        parsed = client._extractor.extract_comments(detail, data)
        for c in parsed:
            if c.comment_id and c.comment_id not in seen:
                seen.add(c.comment_id)
                rows.append({"platform": "zhihu", "post_id": detail.content_id,
                             "content_type": detail.content_type, "comment_id": c.comment_id,
                             "parent_comment_id": c.parent_comment_id or "",
                             "content": c.content, "created_at": c.publish_time})
        return parsed

    offset = ""
    while True:
        page = await client.get_root_comments(detail.content_id, detail.content_type, offset)
        if page == {} and not offset and detail.comment_count == 0:
            return rows
        if not isinstance(page, dict) or "paging" not in page or "data" not in page:
            raise RuntimeError(f"评论响应缺失: {detail.content_id}")
        for root in add(page["data"]):
            if not root.sub_comment_count:
                continue
            child_offset = ""
            while True:
                await asyncio.sleep(delay)
                child = await client.get_child_comments(root.comment_id, child_offset)
                if not isinstance(child, dict) or "paging" not in child or "data" not in child:
                    raise RuntimeError(f"回复响应缺失: {detail.content_id}/{root.comment_id}")
                add(child["data"])
                if child["paging"].get("is_end") is True:
                    break
                next_offset = client._extractor.extract_offset(child["paging"])
                if not next_offset or next_offset == child_offset:
                    raise RuntimeError(f"回复分页停滞: {detail.content_id}/{root.comment_id}")
                child_offset = next_offset
        if page["paging"].get("is_end") is True:
            return rows
        next_offset = client._extractor.extract_offset(page["paging"])
        if not next_offset or next_offset == offset:
            raise RuntimeError(f"评论分页停滞: {detail.content_id}")
        offset = next_offset
        await asyncio.sleep(delay)


async def detail_zhihu(crawler, candidate):
    if candidate.content_type == "article":
        return await crawler.get_note_detail(candidate.content_url, asyncio.Semaphore(1))
    url_path = candidate.content_url.split("www.zhihu.com", 1)[-1]
    html = await crawler.zhihu_client.get(url_path, return_response=True)
    detail = crawler._extractor.extract_answer_content_from_html(html)
    if detail and not detail.title:
        raw = Selector(text=html).xpath("//script[@id='js-initialData']/text()").get(default="")
        entities = json.loads(raw).get("initialState", {}).get("entities", {}) if raw else {}
        answer = entities.get("answers", {}).get(detail.content_id, {})
        question = answer.get("question") or {}
        if not isinstance(question, dict):
            question = entities.get("questions", {}).get(str(question), {})
        detail.title = question.get("title") or (entities.get("questions", {}).get(detail.question_id) or {}).get("title") or ""
    return detail


async def collect(crawler, args, out):
    keywords = [w.strip() for w in args.keywords.split(",") if w.strip()]
    seen = set()
    for old_file in args.exclude_posts or []:
        for line in Path(old_file).read_text(encoding="utf-8").splitlines():
            if line.strip():
                previous = json.loads(line)
                if previous.get("platform") == args.platform:
                    seen.add(str(previous["post_id"]))
    saved = 0
    for keyword in keywords:
        search_id = get_search_id() if args.platform == "xhs" else None
        for page_number in range(args.start_page, args.start_page + args.max_pages):
            if args.platform == "xhs":
                page = await crawler.xhs_client.get_note_by_keyword(
                    keyword=keyword, search_id=search_id, page=page_number, sort=SearchSortType.GENERAL)
                if not isinstance(page, dict):
                    raise RuntimeError("搜索响应无效")
                candidates = page.get("items") or []
            else:
                candidates = await crawler.zhihu_client.get_note_by_keyword(keyword=keyword, page=page_number)
            for item in candidates:
                if args.platform == "xhs":
                    if item.get("model_type") in ("rec_query", "hot_query"):
                        continue
                    pid, token = item.get("id"), item.get("xsec_token")
                    if not pid or not token or pid in seen:
                        continue
                    seen.add(pid)
                    detail = await crawler.get_note_detail_async_task(
                        pid, item.get("xsec_source") or "pc_search", token, asyncio.Semaphore(1))
                    if not detail:
                        continue
                    comments = await comments_xhs(crawler.xhs_client, pid, token, args.delay)
                    post = {"platform": "xhs", "post_id": pid,
                            "title": detail.get("title") or (detail.get("desc") or "")[:255],
                            "body": detail.get("desc") or "",
                            "url": f"https://www.xiaohongshu.com/explore/{pid}",
                            "source_keyword": keyword,
                            "comment_count_reported": (detail.get("interact_info") or {}).get("comment_count")}
                else:
                    if (item.content_type not in ("answer", "article") or not item.content_id
                            or not item.content_url or item.content_id in seen):
                        continue
                    pid = item.content_id
                    seen.add(pid)
                    detail = await detail_zhihu(crawler, item)
                    if not detail or not detail.content_text:
                        continue
                    comments = await comments_zhihu(crawler.zhihu_client, detail, args.delay)
                    post = {"platform": "zhihu", "post_id": pid,
                            "content_type": detail.content_type, "question_id": detail.question_id,
                            "title": detail.title or item.title, "body": detail.content_text,
                            "url": detail.content_url or item.content_url,
                            "source_keyword": keyword, "comment_count_reported": detail.comment_count}
                append(out / "posts.jsonl", [post])
                append(out / "comments.jsonl", comments)
                saved += 1
                print(f"{args.platform}: {saved}/{args.batch_size} {pid} 评论 {len(comments)}", flush=True)
                if saved >= args.batch_size:
                    return saved
                await asyncio.sleep(args.delay)
            if not candidates or (args.platform == "xhs" and not page.get("has_more", False)):
                break
            await asyncio.sleep(args.delay)
    return saved


async def run(args, out):
    config.PLATFORM = args.platform
    config.ENABLE_CDP_MODE = config.CDP_CONNECT_EXISTING = True
    config.CDP_DEBUG_PORT = 9222
    config.AUTO_CLOSE_BROWSER = config.SAVE_LOGIN_STATE = False
    config.ENABLE_IP_PROXY = False
    config.MAX_CONCURRENCY_NUM = 1
    config.CRAWLER_MAX_SLEEP_SEC = args.delay
    crawler = XiaoHongShuCrawler() if args.platform == "xhs" else ZhihuCrawler()
    async with async_playwright() as playwright:
        try:
            crawler.browser_context = await crawler.launch_browser_with_cdp(
                playwright, None, crawler.user_agent, headless=config.CDP_HEADLESS)
            crawler.context_page = await crawler.browser_context.new_page()
            url = crawler.index_url if args.platform == "xhs" else crawler.index_url + "/search?q=python&type=content"
            await crawler.context_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if args.platform == "xhs":
                crawler.xhs_client = await crawler.create_xhs_client(None)
                await crawler.xhs_client.update_cookies(crawler.browser_context, urls=crawler.cookie_urls)
            else:
                crawler.zhihu_client = await crawler.create_zhihu_client(None)
                await crawler.zhihu_client.update_cookies(crawler.browser_context, urls=crawler.cookie_urls)
            saved = await collect(crawler, args, out)
            print(f"完成 {saved} 条，目录 {out}", flush=True)
        finally:
            page = getattr(crawler, "context_page", None)
            if page and not page.is_closed():
                await page.close()
            manager = getattr(crawler, "cdp_manager", None)
            if manager:
                await manager.cleanup(force=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=("xhs", "zhihu"))
    parser.add_argument("--keywords", default="具身智能 面经,具身智能 面试,VLA 面经,世界模型 面试,灵巧手 面试")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--exclude-posts", nargs="+", help="此前各批次的 posts.jsonl，可传多个")
    parser.add_argument("--out", type=Path, help="本批输出目录；默认自动生成唯一目录")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 50 or args.start_page < 1 or args.max_pages < 1 or args.delay < 0:
        parser.error("batch-size 需为 1..50，页数需为正数，delay 不能为负数")
    out = args.out or ROOT / "data" / "batch50" / args.platform / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if out.exists() and any(out.iterdir()):
        parser.error(f"输出目录非空：{out}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "posts.jsonl").touch()
    (out / "comments.jsonl").touch()
    asyncio.run(run(args, out))


if __name__ == "__main__":
    main()
