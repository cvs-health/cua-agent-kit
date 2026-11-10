# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

[CmdletBinding()]
param(
    [string]$PythonExe = 'python',
    [string]$InstallRoot
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\host-common.ps1"
Assert-CuaWindows
$root = Get-CuaHostRoot $InstallRoot
New-Item -ItemType Directory -Force -Path $root | Out-Null
$venv = Join-Path $root 'venv'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & $PythonExe -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated host environment.' }
}
& $python -m pip install -r "$PSScriptRoot\requirements-host.txt"
if ($LASTEXITCODE -ne 0) { throw 'Host dependency installation failed.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Host dependencies are inconsistent.' }
$importProbe = @'
import sys,pywinauto,win32api,comtypes
from importlib.metadata import version
print(sys.executable)
print('computer_server='+version('cua-computer-server'))
print('pywinauto='+version('pywinauto'))
'@
& $python -c $importProbe
if ($LASTEXITCODE -ne 0) { throw 'Host imports failed.' }
Write-Host "Host installed at $root. No server was started or stopped."
Write-Host 'Next: run start.ps1 as the same Windows user.'
