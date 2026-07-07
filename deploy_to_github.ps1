$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Foreign Freelance Radar GitHub deploy helper" -ForegroundColor Cyan
Write-Host ""
Write-Host "Create an empty GitHub repository first, then paste its HTTPS URL here."
Write-Host "Example: https://github.com/YOUR_USERNAME/foreign-freelance-radar.git"
Write-Host ""

$remote = Read-Host "GitHub repository HTTPS URL"
if ([string]::IsNullOrWhiteSpace($remote)) {
  throw "Repository URL is empty."
}

Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".git")) {
  git init
}

git add foreign_freelance_radar.py README.md .gitignore .github/workflows/freelance-radar.yml deploy_to_github.ps1
git commit -m "Add foreign freelance radar cloud workflow"

$existing = git remote
if ($existing -contains "origin") {
  git remote set-url origin $remote
} else {
  git remote add origin $remote
}

git branch -M main
git push -u origin main

Write-Host ""
Write-Host "Pushed. Now add GitHub Actions secrets:" -ForegroundColor Green
Write-Host "TELEGRAM_BOT_TOKEN"
Write-Host "TELEGRAM_CHAT_ID"
Write-Host ""
Write-Host "Then run Actions → Foreign Freelance Radar → Run workflow."
