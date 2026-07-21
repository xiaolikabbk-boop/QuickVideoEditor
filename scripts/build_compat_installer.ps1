param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?$')]
    [string]$Version,

    [string]$SourceDir = 'dist\批量配乐工具',

    [string]$OutputDir = 'release'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$OutputDir = [IO.Path]::GetFullPath((Join-Path $Root $OutputDir))
$CompatDir = Join-Path $OutputDir "QuickVideoEditor-v$Version-Compatible-Setup"
if (-not $CompatDir.StartsWith($OutputDir, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Compatible output path is outside the release directory.'
}
if (Test-Path -LiteralPath $CompatDir) {
    Remove-Item -LiteralPath $CompatDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $CompatDir | Out-Null

$Candidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$CompilerPath = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $CompilerPath) { throw 'Inno Setup 6 was not found.' }

$env:APP_VERSION = $Version
$env:APP_SOURCE_DIR = $SourceDir
$env:INSTALLER_OUTPUT_DIR = $CompatDir
& $CompilerPath (Join-Path $Root 'installer\QuickVideoEditorCompat.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

Copy-Item -LiteralPath (Join-Path $Root 'installer\INSTALLATION.zh-CN.txt') -Destination (Join-Path $CompatDir 'INSTALLATION.zh-CN.txt') -Force

$Archive = Join-Path $OutputDir "QuickVideoEditor-v$Version-Compatible-Setup.zip"
Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
Compress-Archive -LiteralPath $CompatDir -DestinationPath $Archive -CompressionLevel NoCompression
$Hash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$Archive.sha256" -Value "$Hash  $([IO.Path]::GetFileName($Archive))" -Encoding ASCII
Write-Host "Compatible installer complete: $Archive"
Write-Host "SHA-256: $Hash"
