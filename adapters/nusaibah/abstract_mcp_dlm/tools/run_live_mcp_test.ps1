$ErrorActionPreference = "Stop"

$project = "E:\nusaibah_projects\demo_asset_project"
$assetRoot = "$project\pipeline_agent_v1\abstract_mcp_dlm"
$runDir = "$assetRoot\run_profiles"
$assetsRepo = "C:\xampp\htdocs\assets"
$assetsEnv = "$assetsRepo\.env"
$projectEnv = "$project\.env"

$proxyProcess = $null
$workerProcess = $null

function Import-DotEnvFile([string] $Path, [string[]] $Names) {
  if (-not (Test-Path -LiteralPath $Path)) { return }

  Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }

    $parts = $line -split "=", 2
    $name = $parts[0].Trim()
    $value = $parts[1].Trim().Trim('"').Trim("'")

    if ($Names -contains $name) {
      Set-Item -Path "Env:$name" -Value $value
    }
  }
}

function Stop-PortListener([int] $Port) {
  $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" } |
    Select-Object -First 1

  if ($null -ne $connection) {
    Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
  }
}

function Wait-HttpOk([string] $Url, [int] $Seconds = 20) {
  for ($i = 0; $i -lt $Seconds; $i++) {
    try {
      Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 2 | Out-Null
      return $true
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  return $false
}

function Wait-ProxyCacheReady([string] $Url, [int] $Seconds = 60) {
  for ($i = 0; $i -lt $Seconds; $i++) {
    try {
      $health = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 3
      if ($health.cache_ready -eq $true) { return $true }
    } catch {
      # The proxy prefetches Core lake context before opening the runtime path.
    }
    Start-Sleep -Seconds 1
  }
  return $false
}

function Write-Utf8NoBom([string] $Path, [string] $Text) {
  $encoding = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText($Path, $Text + [Environment]::NewLine, $encoding)
}

Import-DotEnvFile $projectEnv @(
  "OBS_BASE_URL", "OBS_API_KEY_HEADER", "OBS_API_KEY", "OBS_CLIENT_ID", "ENTITY_KEY",
  "DLM_BASE_URL", "DLM_API_BASE_URL", "DLM_API_KEY_HEADER", "DLM_API_KEY", "DLM_CLIENT_ID"
)

Import-DotEnvFile $assetsEnv @(
  "APP_URL",
  "PYTHON_ADAPTER_LOCAL_WORKER_URL", "PYTHON_ADAPTER_LOCAL_WORKER_KEY_ID",
  "PYTHON_ADAPTER_LOCAL_WORKER_SHARED_SECRET", "PYTHON_ADAPTER_LOCAL_WORKER_AUTH_HEADER",
  "PYTHON_ADAPTER_LOCAL_WORKER_AUTH_TOKEN", "PYTHON_ADAPTER_LOCAL_WORKER_MAX_AGE_SECONDS",
  "PYTHON_ADAPTER_MCP_TOOL_BRIDGE_HEADER", "PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TOKEN",
  "PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TIMESTAMP_HEADER", "PYTHON_ADAPTER_MCP_TOOL_BRIDGE_NONCE_HEADER",
  "PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TIMEOUT_SECONDS"
)

$assetsBase = if ($env:OBS_BASE_URL) { $env:OBS_BASE_URL.TrimEnd("/") } elseif ($env:APP_URL) { $env:APP_URL.TrimEnd("/") } else { "http://localhost:7080" }

if (-not $env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TOKEN) {
  throw "PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TOKEN is missing from $assetsEnv."
}
if (-not $env:PYTHON_ADAPTER_LOCAL_WORKER_URL) {
  throw "PYTHON_ADAPTER_LOCAL_WORKER_URL is missing from $assetsEnv."
}

$env:OBS_MCP_TOOL_BRIDGE_URL = "$assetsBase/api/v1/observability/internal/python-adapter/mcp-tools/invoke"
$env:OBS_MCP_TOOL_BRIDGE_HEADER = if ($env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_HEADER) { $env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_HEADER } else { "X-OBS-Mcp-Tool-Token" }
$env:OBS_MCP_TOOL_BRIDGE_TOKEN = $env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TOKEN
$env:OBS_MCP_TOOL_BRIDGE_TIMESTAMP_HEADER = if ($env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TIMESTAMP_HEADER) { $env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TIMESTAMP_HEADER } else { "X-OBS-Mcp-Tool-Timestamp" }
$env:OBS_MCP_TOOL_BRIDGE_NONCE_HEADER = if ($env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_NONCE_HEADER) { $env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_NONCE_HEADER } else { "X-OBS-Mcp-Tool-Nonce" }
$env:OBS_MCP_TOOL_BRIDGE_TIMEOUT_SECONDS = if ($env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TIMEOUT_SECONDS) { $env:PYTHON_ADAPTER_MCP_TOOL_BRIDGE_TIMEOUT_SECONDS } else { "30" }
$env:DLM_PROXY_ENV_FILE = $projectEnv

try {
  $proxyPort = 8787
  Stop-PortListener $proxyPort
  $proxyProcess = Start-Process `
    -FilePath "$project\.venv\Scripts\python.exe" `
    -ArgumentList @("$assetRoot\tools\generic_lakes_server.py") `
    -WorkingDirectory $project `
    -WindowStyle Hidden `
    -PassThru

  if (-not (Wait-ProxyCacheReady "http://127.0.0.1:$proxyPort/health" 60)) {
    throw "Local DLM lakes proxy cache did not become ready on port $proxyPort."
  }

  $workerUri = [Uri] $env:PYTHON_ADAPTER_LOCAL_WORKER_URL
  $workerPort = $workerUri.Port
  $workerHost = if ($workerUri.Host -in @("localhost", "127.0.0.1")) { "127.0.0.1" } else { $workerUri.Host }
  $workerPath = if ($workerUri.AbsolutePath) { $workerUri.AbsolutePath } else { "/execute" }

  Stop-PortListener $workerPort

  $workerArgs = @(
    "--host", $workerHost,
    "--port", [string] $workerPort,
    "--path", $workerPath,
    "--adapter-root", $assetRoot,
    "--key-id", $env:PYTHON_ADAPTER_LOCAL_WORKER_KEY_ID,
    "--shared-secret", $env:PYTHON_ADAPTER_LOCAL_WORKER_SHARED_SECRET,
    "--auth-header", $env:PYTHON_ADAPTER_LOCAL_WORKER_AUTH_HEADER,
    "--auth-token", $env:PYTHON_ADAPTER_LOCAL_WORKER_AUTH_TOKEN
  )

  if ($env:PYTHON_ADAPTER_LOCAL_WORKER_MAX_AGE_SECONDS) {
    $workerArgs += @("--max-age-seconds", $env:PYTHON_ADAPTER_LOCAL_WORKER_MAX_AGE_SECONDS)
  }

  $workerProcess = Start-Process `
    -FilePath "$project\.venv\Scripts\obs-runtime-worker.exe" `
    -ArgumentList $workerArgs `
    -WorkingDirectory $project `
    -WindowStyle Hidden `
    -PassThru

  if (-not (Wait-HttpOk $env:PYTHON_ADAPTER_LOCAL_WORKER_URL 20)) {
    Write-Host "local_worker URL did not answer GET health; continuing because signed POST endpoint may reject GET by design."
  }

  $authHeaderName = if ($env:OBS_API_KEY_HEADER) { $env:OBS_API_KEY_HEADER } else { "Authorization" }
  $entityKey = if ($env:ENTITY_KEY) { $env:ENTITY_KEY } else { "entity-1" }

  $headers = @{
    "Accept" = "application/json"
    "Content-Type" = "application/json"
    "X-Client-Id" = $env:OBS_CLIENT_ID
  }
  $headers[$authHeaderName] = $env:OBS_API_KEY

  $body = @{
    entity_key = $entityKey
    asset_key = "nusaibah.abstract_mcp_dlm"
    asset_version = "0.1.0"
    mode = "balanced"
    route = "agent"
    inputs = @{
      tool_request = @{
        records = @(
          @{
            capability_ref = "dlm.lakes.list"
            response_format = "json"
            input = @{ limit = 5; page = 1 }
          }
          @{
            capability_ref = "dlm.lakes.list"
            response_format = "json"
            input = @{ limit = 5; page = 2 }
          }
        )
      }
    }
  } | ConvertTo-Json -Depth 30

  $launch = Invoke-RestMethod `
    -Method Post `
    -Uri "$assetsBase/api/v1/observability/assets/execute" `
    -Headers $headers `
    -Body $body

  Write-Host "Started run:" $launch.data.run_uuid

  $resultUrl = $launch.data.links.result
  $statusUrl = $launch.data.links.status

  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 2
    $status = Invoke-RestMethod -Method Get -Uri $statusUrl -Headers $headers
    $state = $status.data.current_state
    Write-Host "Current state: $state"
    if ($state -in @("completed", "failed", "error", "cancelled", "timed_out")) { break }
  }

  $result = Invoke-RestMethod -Method Get -Uri $resultUrl -Headers $headers
  $resultJson = $result | ConvertTo-Json -Depth 80
  $resultPath = "$runDir\abstract_mcp_dlm.live_run.result.json"
  Write-Utf8NoBom $resultPath $resultJson

  Write-Host "Saved result to:" $resultPath
  Write-Host ""
  Write-Host "Run result:"
  $result.data | ConvertTo-Json -Depth 50

  $records = $result.data.outputs.tool_results.records
  if ($records -and $records.Count -gt 0) {
    Write-Host ""
    Write-Host "MCP runtime proof:"
    $runtimeResult = $records[0].result
    @{
      authority = $records[0].authority
      status = $records[0].status
      record_count = $runtimeResult.record_count
      runtime_mcp_tool = $runtimeResult.provenance.runtime_mcp_tool
      lease_status = $runtimeResult.provenance.lease_status
      first_lake = if ($runtimeResult.records -and $runtimeResult.records.Count -gt 0) { $runtimeResult.records[0].title } else { $null }
      second_page_first_lake = if ($records.Count -gt 1 -and $records[1].result.records -and $records[1].result.records.Count -gt 0) { $records[1].result.records[0].title } else { $null }
    } | ConvertTo-Json -Depth 10
  } else {
    Write-Host "No MCP record was returned."
  }
} finally {
  if ($null -ne $workerProcess -and -not $workerProcess.HasExited) {
    Stop-Process -Id $workerProcess.Id -Force -ErrorAction SilentlyContinue
  }
  if ($null -ne $proxyProcess -and -not $proxyProcess.HasExited) {
    Stop-Process -Id $proxyProcess.Id -Force -ErrorAction SilentlyContinue
  }
}
