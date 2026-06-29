# One-time: authenticate GitHub CLI (portable binary in vault workspace)
$gh = "..\..\..\..\..\..\..\04-workspace\gh.exe"
if (-not (Test-Path $gh)) {
    $gh = "c:\Users\aniru\OneDrive\Documents\Everything\04-workspace\gh.exe"
}

Write-Host "Checking GitHub auth..."
& $gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run: $gh auth login -h github.com -p https -w"
    exit 1
}

Write-Host "Creating public repo and pushing main..."
& $gh repo create anirudh-devanand/agent-trace-replay --public --description "Kafka-backed platform for replaying AI agent tool-call traces with failure injection" --source=. --remote=origin --push

if ($LASTEXITCODE -eq 0) {
    Write-Host "Done: https://github.com/anirudh-devanand/agent-trace-replay"
}
