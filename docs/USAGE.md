# 使用说明

> 目标：用已登录的 Chrome，按批抓取小红书 / 知乎的公开帖子与评论，输出可回溯的 JSONL，并生成降噪 digest 与统计表。

## 1. 环境

| 项 | 要求 |
|---|---|
| Python | 3.11+（MediaCrawler 的要求） |
| Node.js | 知乎请求签名需要 |
| Chrome | 已登录目标平台，开启远程调试 |
| MediaCrawler | 提供平台客户端与 CDP 连接 |

安装：

```bash
git clone https://github.com/NanmiCoder/MediaCrawler.git
git clone https://github.com/BlossomsGarden/Rednote-Zhihu-Crawler.git

cd Rednote-Zhihu-Crawler
./install.sh ../MediaCrawler          # macOS / Linux
# PowerShell: .\install.ps1 -MediaCrawler ..\MediaCrawler
```

```bash
cd ../MediaCrawler
uv sync                # 或 pip install -r requirements.txt
```

## 2. 浏览器

1. 打开 `chrome://inspect/#remote-debugging`。
2. 勾选 **Allow remote debugging for this browser instance**。
3. 保持窗口打开，确认已登录要采集的平台。

脚本默认连接 `127.0.0.1:9222`，复用该浏览器上下文；运行结束只关闭自己创建的标签页，不关闭 Chrome，也不会把 Cookie 或 `xsec_token` 写入结果。

> 小红书与知乎请分开运行，不要同时占用同一个浏览器会话。

## 3. 采集一批

在 MediaCrawler 根目录执行。

**PowerShell**

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\batch50_posts_comments.py `
  --platform xhs `
  --keywords "VLA 面经,世界模型 面试,灵巧手 面经" `
  --batch-size 50 `
  --max-pages 8 `
  --delay 2 `
  --out "data\batch50\xhs\r1"
```

**bash**

```bash
python -X utf8 tools/batch50_posts_comments.py \
  --platform zhihu \
  --keywords "具身智能 面经,VLA 八股" \
  --batch-size 50 \
  --max-pages 8 \
  --delay 2 \
  --out data/batch50/zhihu/r1
```

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--platform` | 必填 | `xhs` 或 `zhihu`，一次只跑一个 |
| `--keywords` | 内置示例 | 英文逗号分隔 |
| `--batch-size` | `50` | 本批保存帖数，范围 1–50 |
| `--start-page` | `1` | 每个关键词的起始搜索页 |
| `--max-pages` | `20` | 每个关键词最多翻页数 |
| `--delay` | `2` | 请求间隔（秒） |
| `--exclude-posts` | 无 | 历史 `posts.jsonl`，可多个 |
| `--out` | 自动时间戳目录 | 必须为空目录 |

### 关键词策略（重要）

- 脚本按关键词顺序搜索；**`saved >= batch-size` 立即返回**。
- 因此通常**第一个关键词就填满整批**，后续关键词不会生效；每轮请把最想覆盖的词放第一位。
- 想覆盖更多主题，用多轮 + 换首关键词 + `--exclude-posts`，而不是把所有词塞进一次运行。
- `--start-page` 是每个关键词各自的起始页，不是全局页号。

## 4. 跨批排重

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\batch50_posts_comments.py `
  --platform xhs `
  --keywords "VLA 秋招,具身智能 offer" `
  --exclude-posts "data\batch50\xhs\r1\posts.jsonl" `
  --out "data\batch50\xhs\r2"
```

多批：

```bash
python -X utf8 tools/batch50_posts_comments.py \
  --platform zhihu \
  --keywords "VLA 八股" \
  --exclude-posts data/batch50/zhihu/r1/posts.jsonl \
                 data/batch50/zhihu/r2/posts.jsonl \
  --out data/batch50/zhihu/r3
```

排重只比较同平台的 `post_id`，不会误伤另一平台。

## 5. 输出

不传 `--out` 时，自动新建 `data/batch50/<platform>/<timestamp>/`。

```text
data/batch50/xhs/r1/
├─ posts.jsonl
└─ comments.jsonl
```

**posts.jsonl**

| 字段 | 说明 |
|---|---|
| `platform` | `xhs` / `zhihu` |
| `post_id` | 帖子 ID |
| `title` / `body` | 标题 / 详情正文（不使用搜索摘要） |
| `url` | 原帖链接 |
| `source_keyword` | 命中关键词 |
| `comment_count_reported` | 平台显示评论数 |
| `content_type` / `question_id` | 仅知乎：`answer` / `article`、问题 ID |

**comments.jsonl**

| 字段 | 说明 |
|---|---|
| `platform` | `xhs` / `zhihu` |
| `post_id` | 所属帖子 |
| `comment_id` | 评论 ID（`cid`） |
| `parent_comment_id` | 父评论；一级评论为空 |
| `content` / `created_at` | 内容 / 时间 |
| `content_type` | 仅知乎 |

零评论时 `comments.jsonl` 为空文件，仍会创建。

## 6. Digest：降噪 + 排序

```bash
python -X utf8 tools/digest_for_analysis.py \
  data/batch50/xhs/r1 data/batch50/xhs/r2 \
  --min-score 2 \
  --min-comment-score 1 > digest.txt
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--min-score` | `2` | 帖子相关性阈值；越大越严格 |
| `--min-comment-score` | `1` | 评论关键词阈值 |
| `--include-low-comments` | 关 | 保留被判定为低价值的评论 |

输出按帖子相关性从高到低排列；每帖含标题、URL、`post_id`、`source_keyword`、正文与高分评论。评论行带 `cid` 与父评论 ID。

低价值判定（`is_low_value`）：

- 长度 < 12 字符；
- 纯表情 / 标点 / 数字；
- 蹲、mark、码、顶、打卡、接好运、谢谢、感谢、好的、收到、牛、强、恭喜、加油、同问、求、+1；
- 纯情绪（哈哈哈、笑死、绷不住、羡慕、同款……）；
- 去除表情后有效字符 < 8。

原始 JSONL 不会被修改；过滤只影响 digest 视图。

## 7. 统计表

```bash
python -X utf8 tools/report_stats.py data/batch50/xhs data/batch50/zhihu
```

- 传入批次目录或其父目录（自动发现子目录）。
- 输出 Markdown：平台、批次、帖子、评论、低价值评论、占比。
- 同一批次若混有平台，会按平台拆行。

示例（合成数据）：

```text
| 平台 | 批次 | 帖子 | 评论 | 低价值评论 | 占比 |
|---|---|---:|---:|---:|---:|
| 小红书 | demo_batch | 2 | 5 | 3 | 60% |
| 知乎 | demo_batch | 1 | 1 | 0 | 0% |
| **合计** | — | **3** | **6** | **3** | **50%** |
```

## 8. 演示数据

```bash
python -X utf8 tools/digest_for_analysis.py examples/demo_batch
python -X utf8 tools/report_stats.py examples/demo_batch
```

`examples/demo_batch` 为**合成数据**，仅用于验证工具链，与任何真实帖子无关。

## 9. 常见问题

<details>
<summary><b>CDP 连接失败 / 找不到 9222</b></summary>

- 确认 Chrome 已勾选 **Allow remote debugging for this browser instance**。
- 确认没有其他程序占用 9222；Chrome 144+ 使用 WebSocket 调试端口。
- 确认脚本运行在 MediaCrawler 根目录，且 `.venv` 依赖已安装。
- 仍失败时重启 Chrome，再重新允许远程调试。

</details>

<details>
<summary><b>HTTP 461 / 471 / 验证码 / 登录失效</b></summary>

- 平台风控，不是脚本 bug。
- 降低频率（`--delay` 调到 3–5），停止一段时间，或更换已登录账号。
- 不要在短时间内连续跑大量批次。

</details>

<details>
<summary><b>知乎请求签名报错</b></summary>

- 确认已安装 Node.js，且 `node -v` 可用。
- MediaCrawler 的知乎客户端会调用 JS 签名逻辑；Node 缺失时无法请求。

</details>

<details>
<summary><b>输出目录非空</b></summary>

脚本拒绝写入已有内容的目录。换一个 `--out`，或手动清空旧目录。

</details>

<details>
<summary><b>知乎日志特别大</b></summary>

知乎搜索接口的响应会被写入日志，单批日志可能达到 MB 级。不要直接 `cat` / `tail` 全文件；用 `grep "完成"`、`wc -l` 或只读 digest。

</details>

<details>
<summary><b>不足 50 条</b></summary>

关键词覆盖不足、页数不够或平台返回受限。增加关键词 / `--max-pages`，或降低 `--batch-size`。终端会打印实际保存数。

</details>

<details>
<summary><b>图片帖没有题目</b></summary>

脚本只抓文字正文与评论，不做 OCR。正文很短的帖子会在 digest 中标注“可能以图片为主”。

</details>

## 10. 边界

- 只读取当前登录态下公开可见的内容；不访问私信、不绕过权限。
- 评论只包含接口当前返回且可翻到的部分；平台删除、折叠或限制的评论无法保证。
- 单批 50 条是采集上限，不代表平台全部相关内容。
- 帖子是个人经历，公司、轮次、薪资等信息需自行核实。
- 请遵守目标平台条款与 MediaCrawler 的 NON-COMMERCIAL LEARNING LICENSE 1.1。
