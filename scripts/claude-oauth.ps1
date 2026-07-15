# Claude Code を OAuth（claude.ai サブスク）で起動する。
# Cursor 統合ターミナルは ANTHROPIC_API_KEY を注入するため、起動前に外す。
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:ANTHROPIC_AUTH_TOKEN -ErrorAction SilentlyContinue

# 日本語 Windows でのコピー文字化け対策（PowerShell 5.1 のデフォルトは US-ASCII）
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8

& claude @args
