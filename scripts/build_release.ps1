param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?$')]
    [string]$Version,

    [string]$DistPath = 'dist'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$AppName = -join ([char[]](0x6279, 0x91cf, 0x914d, 0x4e50, 0x5de5, 0x5177))
$UpdaterName = -join ([char[]](0x66f4, 0x65b0, 0x52a9, 0x624b))

$VersionLine = Select-String -LiteralPath 'version.py' -Pattern '^APP_VERSION = "([^\"]+)"$'
if (-not $VersionLine -or $VersionLine.Matches[0].Groups[1].Value -ne $Version) {
    throw "APP_VERSION in version.py must equal $Version"
}

$Ffmpeg = Get-Command ffmpeg.exe -ErrorAction Stop
$Ffprobe = Get-Command ffprobe.exe -ErrorAction Stop
$env:FFMPEG_BIN_DIR = Split-Path -Parent $Ffmpeg.Source
if ((Split-Path -Parent $Ffprobe.Source) -ne $env:FFMPEG_BIN_DIR) {
    throw 'ffmpeg.exe and ffprobe.exe must be in the same directory.'
}

$parts = $Version.Split('.')[0..2]
$numeric = @([int]$parts[0], [int]$parts[1], [int]($parts[2] -replace '[^0-9].*$', ''), 0)
$versionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($($numeric -join ',')), prodvers=($($numeric -join ',')), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('080404b0', [
    StringStruct('CompanyName', 'xiaolikabbk-boop'),
    StringStruct('FileDescription', '$AppName'),
    StringStruct('FileVersion', '$Version'),
    StringStruct('InternalName', 'QuickVideoEditor'),
    StringStruct('OriginalFilename', '$AppName.exe'),
    StringStruct('ProductName', '$AppName'),
    StringStruct('ProductVersion', '$Version')
  ])]), VarFileInfo([VarStruct('Translation', [2052, 1200])])]
)
"@
Set-Content -LiteralPath '.version_info.txt' -Value $versionInfo -Encoding UTF8

$UpdaterSpec = "$UpdaterName.spec"
$MainSpec = (Get-ChildItem -LiteralPath $Root -Filter '*.spec' | Where-Object Name -ne $UpdaterSpec).FullName
python -m PyInstaller --noconfirm --clean --distpath $DistPath $UpdaterSpec
python -m PyInstaller --noconfirm --clean --distpath $DistPath $MainSpec
Copy-Item -LiteralPath "$DistPath\$UpdaterName.exe" -Destination "$DistPath\$AppName\$UpdaterName.exe" -Force

$ReleaseDir = Join-Path $Root 'release'
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$AssetName = "QuickVideoEditor-v$Version-win-x64.zip"
$AssetPath = Join-Path $ReleaseDir $AssetName
Remove-Item -LiteralPath $AssetPath -Force -ErrorAction SilentlyContinue
Compress-Archive -LiteralPath "$DistPath\$AppName" -DestinationPath $AssetPath -CompressionLevel Optimal
$Hash = (Get-FileHash -LiteralPath $AssetPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$AssetPath.sha256" -Value "$Hash  $AssetName" -Encoding ASCII
powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\build_installer.ps1" -Version $Version -SourceDir "$DistPath\$AppName" -OutputDir 'release'
powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\build_compat_installer.ps1" -Version $Version -SourceDir "$DistPath\$AppName" -OutputDir 'release'

$Tag = "v$Version"
$PackageUrl = "https://github.com/xiaolikabbk-boop/QuickVideoEditor/releases/download/$Tag/$AssetName"
$NotesPath = Join-Path $Root "release_notes\$Tag.md"
$Notes = if (Test-Path -LiteralPath $NotesPath) { Get-Content -LiteralPath $NotesPath -Raw -Encoding UTF8 } else { "See the GitHub Release page for details." }
$Manifest = [ordered]@{
    version = $Version
    tag = $Tag
    notes = $Notes
    page_url = "https://github.com/xiaolikabbk-boop/QuickVideoEditor/releases/tag/$Tag"
    package_name = $AssetName
    package_url = $PackageUrl
    checksum_url = "$PackageUrl.sha256"
} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $ReleaseDir 'latest.json'), $Manifest, (New-Object Text.UTF8Encoding($false)))

Write-Host "Build complete: $AssetPath"
Write-Host "SHA-256: $Hash"
