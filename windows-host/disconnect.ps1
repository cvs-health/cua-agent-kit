# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0


# Transfer the current RDP session to the console; this is NOT Windows sign-out.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ServerAddress = $(if ($env:WINDOWS_HOST -and $env:WINDOWS_HOST -ne '0.0.0.0') { $env:WINDOWS_HOST } else { '127.0.0.1' }),
    [ValidateRange(1, 65535)][int]$Port = $(if ($env:WINDOWS_PORT) { $env:WINDOWS_PORT } else { 8000 }),
    [string]$InstallRoot
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\host-common.ps1"
Assert-CuaWindows
Assert-CuaAddress $ServerAddress
$sessionId = [Diagnostics.Process]::GetCurrentProcess().SessionId
if ($env:SESSIONNAME -notlike 'RDP-*') {
    throw 'Run from the RDP session you intend to disconnect, not an existing console session.'
}
Invoke-CuaCommand $ServerAddress $Port 'version' | Out-Null
if (-not $PSCmdlet.ShouldProcess("current RDP session $sessionId", 'Transfer to console (disconnect this RDP connection)')) { return }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open PowerShell as administrator as the same Windows user, then run this script.'
}
$root = Get-CuaHostRoot $InstallRoot
New-Item -ItemType Directory -Force -Path $root | Out-Null
$log = Join-Path $root 'disconnect.log'
Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Transferring session $sessionId to console."
Write-Host 'Your RDP connection will disconnect. Applications and the server remain in the signed-in session.'
& "$env:SystemRoot\System32\tscon.exe" $sessionId /dest:console
if ($LASTEXITCODE -ne 0) { throw "tscon failed with exit code $LASTEXITCODE. See $log." }
Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Session transfer command succeeded."
# The console resolution can change on handoff. Do not force a display mode or
# interrupt a workflow: inspect geometry from the controller before the next run.
try {
    $screen = Invoke-CuaCommand $ServerAddress $Port 'get_screen_size'
    Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Server responds; dimensions=$($screen.size.width)x$($screen.size.height). Verify screenshots from the controller."
} catch {
    Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Post-transfer check failed: $($_.Exception.Message)"
    throw
}
