#!/usr/bin/env bash
set -euo pipefail

media_crawler="${1:-}"

if [[ -z "$media_crawler" ]]; then
  echo "用法：./install.sh /path/to/MediaCrawler" >&2
  exit 1
fi

if [[ ! -d "$media_crawler/media_platform" ]]; then
  echo "找不到 $media_crawler/media_platform，请传入 MediaCrawler 仓库根目录。" >&2
  exit 1
fi

mkdir -p "$media_crawler/tools"
cp "$(dirname "$0")"/tools/*.py "$media_crawler/tools/"

echo "已复制到 $media_crawler/tools"
echo "下一步：cd \"$media_crawler\" && uv sync"
