# End-to-end demo: ingest -> normalize -> failure-injection replay
param(
    [string]$ApiBase = "http://localhost:8000",
    [string]$TraceId = "trace_demo_refund"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Waiting for API readiness at $ApiBase"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "$ApiBase/ready" -TimeoutSec 2
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    throw "API not ready at $ApiBase"
}

Write-Host "==> Ingesting sample trace"
$ingest = Invoke-RestMethod -Method Post -Uri "$ApiBase/v1/traces/ingest" `
    -ContentType "application/json" `
    -InFile (Join-Path $root "fixtures\sample_ingest.json")
$ingest | ConvertTo-Json -Compress | Write-Host

Write-Host "==> Waiting for manifest"
$manifestReady = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "$ApiBase/v1/traces/$TraceId/manifest" -TimeoutSec 2
        $manifestReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $manifestReady) {
    throw "manifest not ready for $TraceId"
}

Write-Host "==> Starting failure-injection replay"
$create = Invoke-RestMethod -Method Post -Uri "$ApiBase/v1/replays/" `
    -ContentType "application/json" `
    -InFile (Join-Path $root "fixtures\sample_replay_inject.json")
$create | ConvertTo-Json -Compress | Write-Host
$replayId = $create.replay_id

Write-Host "==> Waiting for replay $replayId"
$detail = $null
for ($i = 0; $i -lt 60; $i++) {
    $detail = Invoke-RestMethod -Uri "$ApiBase/v1/replays/$replayId"
    if ($detail.status -in @("completed", "failed")) {
        break
    }
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "==> Replay result"
Write-Host ("replay_id:  {0}" -f $detail.replay_id)
Write-Host ("status:     {0}" -f $detail.status)
Write-Host ("duration:   {0} ms" -f $detail.duration_ms)
Write-Host ("first fail: {0}" -f $detail.first_failed_step_id)
Write-Host ("summary:    {0}" -f ($detail.summary_json | ConvertTo-Json -Compress))
Write-Host "steps:"
foreach ($step in $detail.steps) {
    $err = $null
    if ($step.actual_result) { $err = $step.actual_result.error_type }
    Write-Host ("  - #{0} {1}: {2} ({3})" -f $step.step_order, $step.step_id, $step.status, $err)
}

Write-Host ""
Write-Host "Demo complete. Grafana: http://localhost:3000 (admin/admin)"
