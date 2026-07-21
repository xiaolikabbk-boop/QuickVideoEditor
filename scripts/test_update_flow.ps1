param(
    [string]$HelperPath = ''
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Work = Join-Path $env:TEMP ("QuickVideoEditor-flow-" + [guid]::NewGuid().ToString('N'))
$AppName = -join ([char[]](0x6279, 0x91cf, 0x914d, 0x4e50, 0x5de5, 0x5177))
$Source = Join-Path $Work "source\$AppName"
$Target = Join-Path $Work "installed\$AppName"

function Invoke-Updater([string]$UpdateSource, [string]$UpdateTarget, [bool]$SimulateFailure = $false) {
    $Arguments = @('--wait-pid', '0', '--source', $UpdateSource, '--target', $UpdateTarget, '--exe', "$AppName.exe")
    if ($SimulateFailure) {
        $Arguments += '--simulate-launch-failure'
    }
    if ($HelperPath) {
        $Process = Start-Process -FilePath $HelperPath -ArgumentList $Arguments -Wait -PassThru
        return $Process.ExitCode
    }
    else {
        python "$Root\updater.py" @Arguments
        return $LASTEXITCODE
    }
}

try {
    New-Item -ItemType Directory -Force -Path $Source, $Target | Out-Null
    Set-Content -LiteralPath (Join-Path $Target 'old-version.txt') -Value 'old'
    Set-Content -LiteralPath (Join-Path $Source 'new-version.txt') -Value 'new'
    Copy-Item -LiteralPath "$env:SystemRoot\System32\whoami.exe" -Destination (Join-Path $Source "$AppName.exe")

    $ExitCode = Invoke-Updater $Source $Target
    if ($ExitCode -ne 0) { throw "Updater exit code: $ExitCode" }
    if (-not (Test-Path -LiteralPath (Join-Path $Target 'new-version.txt'))) { throw 'New directory was not installed.' }
    if (Test-Path -LiteralPath (Join-Path $Target 'old-version.txt')) { throw 'Old directory was not replaced.' }

    $BadSource = Join-Path $Work "bad-source\$AppName"
    New-Item -ItemType Directory -Force -Path $BadSource | Out-Null
    Copy-Item -LiteralPath "$env:SystemRoot\System32\whoami.exe" -Destination (Join-Path $BadSource "$AppName.exe")
    $ExitCode = Invoke-Updater $BadSource $Target $true
    if ($ExitCode -eq 0) { throw 'A broken update should fail.' }
    if (-not (Test-Path -LiteralPath (Join-Path $Target 'new-version.txt'))) { throw 'Rollback did not restore the previous directory.' }
    Write-Host 'Local update flow passed: full replacement and rollback both succeeded.'
}
finally {
    Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue
}
