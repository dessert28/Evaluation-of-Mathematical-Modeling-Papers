param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "未找到 .venv，请先安装项目依赖" }
& $python -m uvicorn backend.app.main:app --reload --port $Port
