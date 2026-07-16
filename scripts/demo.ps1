# End-to-end demo with multiple agent traces and replays
param(
    [string]$ApiBase = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$demoDir = Join-Path $root "fixtures\demo"

function Wait-Ready {
    Write-Host "==> Waiting for API at $ApiBase"
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $null = Invoke-RestMethod -Uri "$ApiBase/ready" -TimeoutSec 2
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "API not ready at $ApiBase"
}

function Wait-Manifest([string]$TraceId) {
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $null = Invoke-RestMethod -Uri "$ApiBase/v1/traces/$TraceId/manifest" -TimeoutSec 2
            return
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "manifest not ready for $TraceId"
}

function Wait-Replay([string]$ReplayId) {
    for ($i = 0; $i -lt 60; $i++) {
        $detail = Invoke-RestMethod -Uri "$ApiBase/v1/replays/$ReplayId"
        if ($detail.status -in @("completed", "failed")) {
            return $detail
        }
        Start-Sleep -Milliseconds 500
    }
    throw "replay $ReplayId did not finish"
}

function Show-ReplaySummary($Detail, [string]$Label) {
    Write-Host ""
    Write-Host "---- $Label ----"
    Write-Host ("trace:      {0}" -f $Detail.trace_id)
    Write-Host ("replay:     {0}" -f $Detail.replay_id)
    Write-Host ("status:     {0}" -f $Detail.status)
    Write-Host ("duration:   {0} ms" -f $Detail.duration_ms)
    Write-Host ("first fail: {0}" -f $Detail.first_failed_step_id)
    Write-Host ("summary:    passed={0} failed={1} steps={2}" -f `
        $Detail.summary_json.passed, $Detail.summary_json.failed, $Detail.summary_json.step_count)
    Write-Host "step breakdown:"
    foreach ($step in $Detail.steps) {
        $err = $null
        if ($step.actual_result) { $err = $step.actual_result.error_type }
        Write-Host ("  #{0,-2} {1,-28} {2,-8} {3}" -f $step.step_order, $step.step_id, $step.status, $err)
    }
}

Wait-Ready

$traces = @(
    "trace_refund_support.json",
    "trace_checkout.json",
    "trace_knowledge_assist.json"
)

Write-Host ""
Write-Host "==> Loading demo agent recordings (traces)"
foreach ($file in $traces) {
    $path = Join-Path $demoDir $file
    $payload = Get-Content $path -Raw | ConvertFrom-Json
    Write-Host ("  ingest {0} ({1} events)" -f $payload.trace_id, $payload.events.Count)
    $null = Invoke-RestMethod -Method Post -Uri "$ApiBase/v1/traces/ingest" `
        -ContentType "application/json" -InFile $path
    Wait-Manifest $payload.trace_id
    Write-Host ("  manifest ready for {0}" -f $payload.trace_id)
}

Write-Host ""
Write-Host "==> Running replays"
$scenarios = @(
    @{ File = "replay_checkout_clean.json"; Label = "Checkout (happy path, no injected failures)" },
    @{ File = "replay_knowledge_slow.json"; Label = "Knowledge assist (slow doc fetch injected)" },
    @{ File = "replay_refund_inject.json"; Label = "Refund support (timeout + bad JSON + HTTP 500)" }
)

foreach ($scenario in $scenarios) {
    $path = Join-Path $demoDir $scenario.File
    $create = Invoke-RestMethod -Method Post -Uri "$ApiBase/v1/replays/" `
        -ContentType "application/json" -InFile $path
    Write-Host ("  queued {0}" -f $create.replay_id)
    $detail = Wait-Replay $create.replay_id
    Show-ReplaySummary $detail $scenario.Label
}

Write-Host ""
Write-Host "==> Demo data is loaded"
Write-Host "Open Grafana: http://localhost:3000  (admin / admin)"
Write-Host "Dashboard: Agent Trace Replay - How to read the platform"
Write-Host "The top of the dashboard explains each chart in plain language."
