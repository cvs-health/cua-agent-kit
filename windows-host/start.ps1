# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

[CmdletBinding()]
param(
    [string]$BindAddress = $(if ($env:WINDOWS_HOST) { $env:WINDOWS_HOST } else { '127.0.0.1' }),
    [ValidateRange(1, 65535)][int]$Port = $(if ($env:WINDOWS_PORT) { $env:WINDOWS_PORT } else { 8000 }),
    [string]$InstallRoot
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\host-common.ps1"
Assert-CuaWindows
Assert-CuaAddress $BindAddress
$python = Get-CuaPython $InstallRoot
$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $Port already has a listener. No process was stopped; use another port or stop your own server."
}
# Child 'python' commands issued by computer_server must resolve to this venv.
$previousPath = $env:PATH
$previousUnbuffered = $env:PYTHONUNBUFFERED
try {
    $env:PATH = (Split-Path $python) + ';' + $previousPath
    $env:PYTHONUNBUFFERED = '1'
    Write-Host "Starting host on ${BindAddress}:$Port in session $([Diagnostics.Process]::GetCurrentProcess().SessionId)."
    Write-Host "Python: $python. Keep this window open; Ctrl+C stops the server."
    & $python -m computer_server.main --host $BindAddress --port $Port
    if ($LASTEXITCODE -ne 0) { throw "computer_server exited with code $LASTEXITCODE." }
} finally {
    $env:PATH = $previousPath
    $env:PYTHONUNBUFFERED = $previousUnbuffered
}
