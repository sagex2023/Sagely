# Run in PowerShell from the unzipped asym_brief folder.
git init -b main
git add -A
git commit -m "Sagely pipeline"
git remote add origin https://github.com/sagex2023/Sagely.git
gh auth status; if ($LASTEXITCODE -ne 0) { gh auth login }
git push -u origin main
gh secret set TRADIER_TOKEN --repo sagex2023/Sagely
gh secret set FINNHUB_API_KEY --repo sagex2023/Sagely
gh secret set BUTTONDOWN_API_KEY --repo sagex2023/Sagely
gh api -X POST repos/sagex2023/Sagely/pages -f build_type=workflow
gh workflow run daily-brief --repo sagex2023/Sagely -f dry_run=true
Write-Host "Dry run started. Open Claude Code in this folder and say: check the dry run log."
