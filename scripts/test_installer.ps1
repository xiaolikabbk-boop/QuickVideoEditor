param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = 'Stop'
$InstallerPath = (Resolve-Path -LiteralPath $InstallerPath).Path
$AppName = -join ([char[]](0x6279, 0x91cf, 0x914d, 0x4e50, 0x5de5, 0x5177))
$UpdaterName = -join ([char[]](0x66f4, 0x65b0, 0x52a9, 0x624b))
$TestRoot = Join-Path $env:TEMP ("QuickVideoEditor-install-" + [guid]::NewGuid().ToString('N'))
$InstallDir = Join-Path $TestRoot 'app'

try {
    New-Item -ItemType Directory -Force -Path $TestRoot | Out-Null
    $Arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/MERGETASKS=!desktopicon', "/DIR=$InstallDir")
    $Installer = Start-Process -FilePath $InstallerPath -ArgumentList $Arguments -Wait -PassThru
    if ($Installer.ExitCode -ne 0) { throw "Installer exit code: $($Installer.ExitCode)" }

    $Main = Join-Path $InstallDir "$AppName.exe"
    $Helper = Join-Path $InstallDir "$UpdaterName.exe"
    $Ffmpeg = Join-Path $InstallDir '_internal\ffmpeg\ffmpeg.exe'
    foreach ($File in @($Main, $Helper, $Ffmpeg)) {
        if (-not (Test-Path -LiteralPath $File)) { throw "Missing installed file: $File" }
    }

    $App = Start-Process -FilePath $Main -PassThru
    Start-Sleep -Seconds 4
    $App.Refresh()
    if ($App.HasExited) { throw "Installed app exited early: $($App.ExitCode)" }
    $Title = $App.MainWindowTitle
    $App.CloseMainWindow() | Out-Null
    $App.WaitForExit(5000) | Out-Null
    if (-not $App.HasExited) {
        $App.Kill()
        $App.WaitForExit()
    }

    $UninstallerPath = Join-Path $InstallDir 'unins000.exe'
    $Uninstaller = Start-Process -FilePath $UninstallerPath -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
    if ($Uninstaller.ExitCode -ne 0) { throw "Uninstaller exit code: $($Uninstaller.ExitCode)" }
    Start-Sleep -Seconds 1
    [pscustomobject]@{
        InstallerExit = $Installer.ExitCode
        WindowTitle = $Title
        MainExePresent = $true
        UpdaterPresent = $true
        FfmpegPresent = $true
        UninstallerExit = $Uninstaller.ExitCode
        InstallDirRemoved = -not (Test-Path -LiteralPath $InstallDir)
    } | Format-List
}
finally {
    $Resolved = [IO.Path]::GetFullPath($TestRoot)
    $TempRoot = [IO.Path]::GetFullPath($env:TEMP)
    if ($Resolved.StartsWith($TempRoot, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $Resolved)) {
        Remove-Item -LiteralPath $Resolved -Recurse -Force -ErrorAction SilentlyContinue
    }
}
