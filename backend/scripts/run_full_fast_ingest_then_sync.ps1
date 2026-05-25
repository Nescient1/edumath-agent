param(
  [string]$Python = "D:\Users\asus\miniconda3\envs\edumath\python.exe",
  [string]$VisionModel = "mimo-v2.5"
)

$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $ProjectRoot

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = Join-Path $ProjectRoot "backend\data\llm_processed\function_derivative\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir "full_fast_ingest_then_sync_$Timestamp.log"

function Write-LogLine {
  param([string]$Message)
  $Message | Tee-Object -FilePath $LogPath -Append
}

function Run-PythonStep {
  param(
    [string]$Name,
    [string[]]$Arguments
  )
  Write-LogLine "[STEP] $Name $(Get-Date -Format s)"
  & $Python @Arguments 2>&1 | Tee-Object -FilePath $LogPath -Append
  $ExitCode = $LASTEXITCODE
  Write-LogLine "[STEP] $Name exit_code=$ExitCode $(Get-Date -Format s)"
  if ($ExitCode -ne 0) {
    Write-LogLine "[WARN] continuing after non-zero exit code from $Name"
  }
}

Write-LogLine "[STEP] workflow start $(Get-Date -Format s)"

Run-PythonStep "full ingest" @(
  "backend\scripts\llm_ingest_function_derivative.py",
  "--topic", "all",
  "--max-pages", "0",
  "--write-db",
  "--vision-first",
  "--vision-model", $VisionModel,
  "--pix2text-mode", "off",
  "--skip-existing-success"
)

Run-PythonStep "normalize postgres knowledge points" @(
  "backend\scripts\normalize_postgres_knowledge_points.py",
  "--apply"
)

Run-PythonStep "embed postgres to chroma" @(
  "backend\scripts\embed_postgres_to_chroma.py"
)

Run-PythonStep "retrieval and recommendation test" @(
  "backend\scripts\test_postgres_rag_recommend.py"
)

Run-PythonStep "quality report" @(
  "backend\scripts\report_ingest_quality.py"
)

Write-LogLine "[STEP] workflow finished $(Get-Date -Format s)"
