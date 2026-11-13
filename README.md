<a id="top"></a>

# Rednote × Zhihu Crawler 🧲

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Reports](https://img.shields.io/badge/Reports-Paid-black)](#-数据与报告)

> 搭配 MediaCrawler，按批采集小红书 / 知乎公开帖子与评论，并完成降噪、排序和统计。
> **工具和pipeline免费开源；采集所得数据与调研报告不随仓库开源。**

---

## 🧩 它做什么

- 📦 **按批采集**：每批最多 50 条不同帖子，正文 + 所有评论和回复。
- 🧹 **跨批排重**：通过历史 `posts.jsonl` 自动筛除跳过已采集的 `post_id`。
- 🗂️ **结构化落盘**：JSONL 结果中帖子与评论用 `post_id` 关联，结论可回溯到原帖。
- 📊 **可复现统计**：一条命令输出帖子数、评论数、低价值评论占比的 Markdown 表。


## 🔁 工作流

```text
Chrome（已打开登录）
      │ CDP 9222
      ▼
batch50_posts_comments.py ──▶ data/batch50/<platform>/<batch>/
                               ├─ posts.jsonl
                               └─ comments.jsonl
                                        │
                          digest_for_analysis.py
                                        │
                              相关性排序 + 降噪 Digest
                                        │
                                人工提取 / 撰写报告
                                        │
                              report_stats.py → 统计表
```

## 📁 目录

```text
Rednote-Zhihu-Crawler/
├─ tools/
│  ├─ batch50_posts_comments.py   # 采集：每批 ≤50 帖 + 全量评论
│  ├─ digest_for_analysis.py      # 分析：相关性排序 + 低价值过滤
│  └─ report_stats.py             # 统计：帖子/评论/低价值占比
├─ docs/
│  ├─ USAGE.md                    # 完整参数、排重、排障
│  └─ ANALYSIS.md                 # 从 digest 到报告的分析流程
├─ examples/
│  ├─ demo_batch/                 # 合成演示数据
│  └─ demo_digest.txt             # 演示输出
├─ install.ps1
├─ install.sh
├─ LICENSE
└─ README.md
```

## 🚀 快速开始

### 0. 前置

| 依赖 | 说明 |
|---|---|
| Python 3.11+ | MediaCrawler 的要求 |
| Node.js | 知乎请求签名 |
| 小红书账号 | 推荐搞两个号，大约爬取 2000 条时会触发风控
| 知乎账号 | 一个即可，知乎不风控（甚至有官方提供的付费爬取结果）
| Chrome | 已登录小红书 / 知乎，并开启远程调试 |
| [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 本仓库不重复实现该平台客户端 |

### 1. 安装

```bash
git clone https://github.com/NanmiCoder/MediaCrawler.git
git clone https://github.com/BlossomsGarden/Rednote-Zhihu-Crawler.git

# 把本仓库的工具复制进 MediaCrawler/tools/
cd Rednote-Zhihu-Crawler
./install.sh ../MediaCrawler          # macOS / Linux
# PowerShell: .\install.ps1 -MediaCrawler ..\MediaCrawler
```

```bash
cd ../MediaCrawler
uv sync                # 或 pip install -r requirements.txt
```

### 2. 开启 Chrome 远程调试

1. 在 Chrome 打开 `chrome://inspect/#remote-debugging`。
2. 勾选 **Allow remote debugging for this browser instance**。
3. 保持 Chrome 窗口打开，登录目标平台。

> 脚本连接 `127.0.0.1:9222`，运行结束不会关闭 Chrome，也不会导出 Cookie。

### 3. 跑一批

```powershell
# PowerShell（Windows）
.\.venv\Scripts\python.exe -X utf8 tools\batch50_posts_comments.py `
  --platform xhs `
  --keywords "VLA 面经,世界模型 面试,灵巧手 面经" `
  --batch-size 50 `
  --out "data\batch50\xhs\r1"
```

```bash
# bash（macOS / Linux）
python -X utf8 tools/batch50_posts_comments.py \
  --platform zhihu \
  --keywords "具身智能 面经,VLA 八股" \
  --batch-size 50 \
  --out data/batch50/zhihu/r1
```

### 4. 下一批：跨批排重

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\batch50_posts_comments.py `
  --platform xhs `
  --keywords "VLA 秋招,具身智能 offer" `
  --exclude-posts "data\batch50\xhs\r1\posts.jsonl" `
  --out "data\batch50\xhs\r2"
```

多个历史批次依次写在 `--exclude-posts` 后面即可。

### 5. 降噪 Digest

```bash
python -X utf8 tools/digest_for_analysis.py data/batch50/xhs/r1 data/batch50/xhs/r2 \
  --min-score 2 --min-comment-score 1 > digest.txt
```

### 6. 复现统计表

```bash
python -X utf8 tools/report_stats.py data/batch50/xhs data/batch50/zhihu
```

## 📊 本次调研规模

> 仅统计数量；**不含**帖子正文、评论内容、链接与调研报告。

| 平台 | 帖子 | 评论 | 低价值评论 | 占比 |
|---|---:|---:|---:|---:|
| 小红书（6 轮） | 318 | 7,889 | 3,710 | 47% |
| 知乎（6 轮） | 267 | 3,368 | 790 | 23% |
| **合计** | **585** | **11,257** | **4,500** | **40%** |

- 采集方式：两平台各 6 轮关键词，每轮最多 50 帖，跨轮按 `post_id` 排重。
- 低价值判定：纯表情 / 标点、单字、蹲 / mark / 感谢 / 同问 / 求链接、纯情绪、广告、重复短句。
- 过滤只作用于最终引用；原始 JSONL 完整保留，可随时回查。

## 🧾 输出格式

**`posts.jsonl`**

| 字段 | 含义 |
|---|---|
| `platform` | `xhs` / `zhihu` |
| `post_id` | 帖子 ID |
| `title` / `body` | 标题 / 正文 |
| `url` | 原帖链接 |
| `source_keyword` | 命中的关键词 |
| `comment_count_reported` | 平台显示的评论数 |
| `content_type` / `question_id` | 仅知乎：`answer` / `article`、问题 ID |

**`comments.jsonl`**

| 字段 | 含义 |
|---|---|
| `platform` | `xhs` / `zhihu` |
| `post_id` | 所属帖子 |
| `comment_id` | 评论 ID（即 `cid`） |
| `parent_comment_id` | 父评论；一级评论为空 |
| `content` / `created_at` | 评论内容 / 时间 |
| `content_type` | 仅知乎 |

完整说明与故障排查见 **[docs/USAGE.md](docs/USAGE.md)**。

## 🧠 分析建议

1. **每轮换首个关键词**：脚本达到 `--batch-size` 立即停止，第一个关键词往往就填满整批。
2. **排重靠 `--exclude-posts`**，不要只靠 `--start-page`；两者可以一起用。
3. **先 digest 再人工读**：把 500 行压到 100 行，低价值评论仍留在原始文件里。
4. **每条结论留 URL**：评论结论同时留 `cid`，否则无法回溯。
5. **单批 50 条 ≠ 全量**：关键词、排序、页数都会影响覆盖，报告里要写清口径。

完整方法（提取字段、归并计频、报告骨架、交付检查）见 **[docs/ANALYSIS.md](docs/ANALYSIS.md)**。

## 🔒 数据与报告

本仓库**只开源工具链**，不包含：

- ❌ 任何真实帖文、评论、账号信息或原帖链接
- ❌ 采集得到的 JSONL 数据集
- ❌ 调研报告、结论、图表

README 中的规模统计仅为数量汇总，需要现成的结构化数据或完整分析报告（付费），可通过仓库 **Issues** 联系作者。


## 📄 License

MediaCrawler 的许可证为 **NON-COMMERCIAL LEARNING LICENSE 1.1**，版权归其作者所有。使用、修改或分发 MediaCrawler 时，请遵守其许可证与免责声明。本仓库自有的采集 / 分析脚本采用 **MIT**，见 [LICENSE](LICENSE)。
依赖项仍遵循各自许可证。

- 仅用于学习与研究目的。
- 仅访问当前登录态下公开可见的内容，不绕过权限、不采集私信或隐私字段。
- 控制请求频率，避免对目标平台造成负担。
- 使用者应自行遵守目标平台的服务条款与适用法律。

[⬆ 回到顶部](#top)
