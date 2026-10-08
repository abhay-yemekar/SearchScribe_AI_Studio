#requires -Version 7.4
[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$ApiPort = 8250,
    [ValidateRange(1024, 65535)][int]$WebPort = 3200,
    [ValidateRange(5, 240)][int]$WaitSeconds = 120,
    [switch]$StatusOnly,
    [switch]$DryRun,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$taskRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$taskBackend = Join-Path $taskRoot 'backend'
$taskFrontend = Join-Path $taskRoot 'frontend'
$taskCache = Join-Path $taskRoot '.cache/runapp'
$taskWebUrl = "http://localhost:$WebPort"
$taskApiUrl = "http://127.0.0.1:$ApiPort"
if ($ApiPort -eq $WebPort) { throw 'API and website must use different ports.' }
if (-not (Test-Path -LiteralPath (Join-Path $taskBackend 'app/main.py'))) {
    throw 'This helper must run from the SearchScribe_AI_Studio checkout.'
}
if ($DryRun) {
    Write-Output "Website: $taskWebUrl | API: $taskApiUrl"
    Write-Output 'Fresh start: mock AI, local auth, Google disabled, backend/codex_runapp_preview.db.'
    Write-Output 'Dry run: no processes, files, port inspection, or browser actions.'
    return
}
if (-not $IsWindows) { throw 'This starter supports the personal Windows checkout only.' }

function Get-PreviewOwner([int]$Port, [string]$Kind) {
    $taskListeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object LocalPort -eq $Port | Select-Object -ExpandProperty OwningProcess -Unique)
    if (-not $taskListeners.Count) { return $null }
    if ($taskListeners.Count -ne 1) { throw "Multiple processes listen on port $Port; none will be changed." }
    $taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($taskListeners[0])" -ErrorAction Stop
    $taskCommand = ([string]$taskProcess.CommandLine).Replace('/', '\')
    $taskOwned = $taskCommand.IndexOf($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase) -ge 0
    $taskMatchesKind = if ($Kind -eq 'api') { $taskCommand -match 'uvicorn|app\.start' } else { $taskCommand -match 'next' }
    if (-not $taskOwned -or -not $taskMatchesKind) {
        throw "Port $Port is occupied by an unverified process. No process will be stopped or reused."
    }
    return [int]$taskListeners[0]
}

function Test-PreviewUrl([string]$Url) {
    try { return (Invoke-WebRequest -Uri $Url -TimeoutSec 3 -MaximumRedirection 2).StatusCode -eq 200 }
    catch { return $false }
}

function Wait-PreviewUrl([string]$Url) {
    $taskDeadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
    do {
        if (Test-PreviewUrl $Url) { return }
        Start-Sleep -Milliseconds 750
    } while ([DateTime]::UtcNow -lt $taskDeadline)
    throw "Preview not ready at $Url. Inspect logs in $taskCache; recorded project processes remain intact."
}

$taskApiOwner = Get-PreviewOwner $ApiPort 'api'
$taskWebOwner = Get-PreviewOwner $WebPort 'web'
if ($StatusOnly) {
    [pscustomobject]@{
        Website = $taskWebUrl
        Api = $taskApiUrl
        ApiProcess = $taskApiOwner
        WebProcess = $taskWebOwner
        ApiReady = [bool]($taskApiOwner -and (Test-PreviewUrl "$taskApiUrl/api/v1/ready"))
        ProxyReady = [bool]($taskWebOwner -and (Test-PreviewUrl "$taskWebUrl/api/v1/ready"))
        WebsiteReady = [bool]($taskWebOwner -and (Test-PreviewUrl $taskWebUrl))
        Mode = 'Existing project settings not changed or inferred'
    }
    return
}

if (-not $taskWebOwner) {
    $taskOtherDev = @(Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" -ErrorAction Stop |
        Where-Object {
            $taskCandidateCommand = ([string]$_.CommandLine).Replace('/', '\')
            $taskCandidateCommand.IndexOf($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
            $taskCandidateCommand -match 'next' -and $taskCandidateCommand -match '(?:^|\s)dev(?:\s|$)'
        })
    if ($taskOtherDev.Count) {
        throw 'A Next.js dev server already runs for this checkout on another port. Use its existing port; no second server was started.'
    }
}

$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
$taskNext = Join-Path $taskFrontend 'node_modules/next/dist/bin/next'
if (-not (Test-Path -LiteralPath $taskPython) -or -not (Test-Path -LiteralPath $taskNext)) {
    throw 'Existing project Python/Node dependencies are required. No packages were installed.'
}
$taskNode = (Get-Command node -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
New-Item -ItemType Directory -Path $taskCache -Force | Out-Null
$taskStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$taskState = [ordered]@{
    Workspace = $taskRoot
    Website = $taskWebUrl
    Api = $taskApiUrl
    ApiProcess = $taskApiOwner
    WebProcess = $taskWebOwner
    ApiMode = if ($taskApiOwner) { 'reused-settings-unconfirmed' } else { 'mock' }
    Database = if ($taskApiOwner) { 'existing-settings-unconfirmed' } else { 'backend/codex_runapp_preview.db' }
}
function Save-PreviewState {
    $taskState | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskCache "ports-$ApiPort-$WebPort.json") -Encoding utf8
}

if (-not $taskApiOwner) {
    $taskChildEnv = @{
        APP_ENV = 'local'
        AI_PROVIDER = 'mock'
        GOOGLE_CLIENT_ID = ''
        GEMINI_API_KEY = ''
        DATABASE_URL = 'sqlite:///' + (Join-Path $taskBackend 'codex_runapp_preview.db').Replace('\', '/')
        SECRET_KEY = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
        CORS_ORIGINS = "$taskWebUrl,http://127.0.0.1:$WebPort"
    }
    $taskMigration = Start-Process -FilePath $taskPython -ArgumentList '-m', 'alembic', 'upgrade', 'head' `
        -WorkingDirectory $taskBackend -Environment $taskChildEnv -WindowStyle Hidden -PassThru -Wait `
        -RedirectStandardOutput (Join-Path $taskCache "migration-$taskStamp.log") `
        -RedirectStandardError (Join-Path $taskCache "migration-$taskStamp-error.log")
    if ($taskMigration.ExitCode -ne 0) { throw "Preview database migration failed; inspect $taskCache. No server was started." }
    $taskApiProcess = Start-Process -FilePath $taskPython `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--app-dir', ('"' + $taskBackend + '"'), '--host', '127.0.0.1', '--port', $ApiPort `
        -WorkingDirectory $taskBackend -Environment $taskChildEnv -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $taskCache "api-$taskStamp.log") `
        -RedirectStandardError (Join-Path $taskCache "api-$taskStamp-error.log")
    $taskState.ApiProcess = $taskApiProcess.Id
    Save-PreviewState
} else {
    Write-Warning "Reusing this project's API on $ApiPort; its existing settings were not changed or independently verified."
}
Wait-PreviewUrl "$taskApiUrl/api/v1/ready"

if (-not $taskWebOwner) {
    $taskWebProcess = Start-Process -FilePath $taskNode `
        -ArgumentList ('"' + $taskNext + '"'), 'dev', '--hostname', '127.0.0.1', '--port', $WebPort `
        -WorkingDirectory $taskFrontend -Environment @{ BACKEND_URL = $taskApiUrl; NEXT_TELEMETRY_DISABLED = '1'; NODE_ENV = 'development' } `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskCache "web-$taskStamp.log") `
        -RedirectStandardError (Join-Path $taskCache "web-$taskStamp-error.log")
    $taskState.WebProcess = $taskWebProcess.Id
    Save-PreviewState
}
Wait-PreviewUrl "$taskWebUrl/api/v1/ready"
Wait-PreviewUrl $taskWebUrl
$taskState.ApiProcess = Get-PreviewOwner $ApiPort 'api'
$taskState.WebProcess = Get-PreviewOwner $WebPort 'web'
Save-PreviewState
Write-Output "SearchScribe ready: $taskWebUrl"
Write-Output "API mode: $($taskState.ApiMode). Logs and project PIDs: $taskCache"
if (-not $NoBrowser) { Start-Process -FilePath $taskWebUrl }
