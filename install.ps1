param(
    [Parameter(Mandatory = $true)]
    [string]$MediaCrawler
)

$source = Join-Path $PSScriptRoot "tools"
$targetRoot = Resolve-Path $MediaCrawler -ErrorAction Stop

if (-not (Test-Path (Join-Path $targetRoot "media_platform"))) {
    throw "找不到 $targetRoot\media_platform，请传入 MediaCrawler 仓库根目录。"
}

$target = Join-Path $targetRoot "tools"
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item (Join-Path $source "*.py") $target -Force

Write-Host "已复制到 $target"
Write-Host "下一步：cd `"$targetRoot`"; uv sync"
