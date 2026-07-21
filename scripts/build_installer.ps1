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
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$Compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $Compiler) {
    $Candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $CompilerPath = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $CompilerPath) {
        throw 'Inno Setup 6 was not found. Install JRSoftware.InnoSetup first.'
    }
}
else {
    $CompilerPath = $Compiler.Source
}

$env:APP_VERSION = $Version
$env:APP_SOURCE_DIR = $SourceDir
$env:INSTALLER_OUTPUT_DIR = $OutputDir
& $CompilerPath (Join-Path $Root 'installer\QuickVideoEditor.iss')
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$Installer = Join-Path $OutputDir "QuickVideoEditor-v$Version-Setup.exe"
$Hash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$Installer.sha256" -Value "$Hash  $([IO.Path]::GetFileName($Installer))" -Encoding ASCII
Write-Host "Installer complete: $Installer"
Write-Host "SHA-256: $Hash"
