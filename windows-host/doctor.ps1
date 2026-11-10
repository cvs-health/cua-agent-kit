# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0


[CmdletBinding()]
param(
    [string]$ServerAddress = $(if ($env:WINDOWS_HOST -and $env:WINDOWS_HOST -ne '0.0.0.0') { $env:WINDOWS_HOST } else { '127.0.0.1' }),
    [ValidateRange(1, 65535)][int]$Port = $(if ($env:WINDOWS_PORT) { $env:WINDOWS_PORT } else { 8000 }),
    [string]$InstallRoot,
    [switch]$Screenshot
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\host-common.ps1"
Assert-CuaWindows
Assert-CuaAddress $ServerAddress
$python = Get-CuaPython $InstallRoot
Write-Host "Current user: $env:USERNAME; session: $([Diagnostics.Process]::GetCurrentProcess().SessionId)"
$importProbe = @'
import sys,pywinauto,win32api,comtypes
from importlib.metadata import version
print('Host Python: '+sys.executable)
print('computer_server='+version('cua-computer-server'))
print('pywinauto='+version('pywinauto'))
'@
& $python -c $importProbe
if ($LASTEXITCODE -ne 0) { throw 'Local host dependency imports failed.' }
$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if (-not $listener) { throw "No local listener on port $Port. Start the server first." }
$listener | Select-Object LocalAddress, LocalPort, OwningProcess | Format-Table
$version = Invoke-CuaCommand $ServerAddress $Port 'version'
Write-Host "Server reachable locally: package=$($version.package)"
# Confirm remote commands use this same Python and the intended desktop session.
$probe = @'
import sys,os,json,ctypes
session=ctypes.c_uint()
if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),ctypes.byref(session)):
    raise RuntimeError('Cannot identify server command session')
print(json.dumps(dict(python=sys.executable,user=os.environ.get('USERNAME'),session=session.value)))
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probe))
$command = 'python -c "import base64;exec(base64.b64decode(''{0}''))"' -f $encoded
$result = Invoke-CuaCommand $ServerAddress $Port 'run_command' @{ command = $command; timeout = 8 }
if ($result.return_code -ne 0) { throw 'Server command execution failed.' }
$remote = $result.stdout.Trim() | ConvertFrom-Json
if (-not [string]::Equals($python, $remote.python, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Server commands use $($remote.python), expected $python. Start the server with start.ps1."
}
if ($remote.session -ne [Diagnostics.Process]::GetCurrentProcess().SessionId) {
    throw "Server commands run in session $($remote.session), not this desktop session."
}
Write-Host "Command Python/session verified: $($remote.python), session $($remote.session)"
$screen = Invoke-CuaCommand $ServerAddress $Port 'get_screen_size'
Write-Host "Desktop dimensions: $($screen.size.width) x $($screen.size.height)"
if ($Screenshot) {
    $capture = Invoke-CuaCommand $ServerAddress $Port 'screenshot'
    $bytes = [Convert]::FromBase64String($capture.image_data)
    if ($bytes.Length -lt 24 -or [BitConverter]::ToString($bytes, 0, 8) -ne '89-50-4E-47-0D-0A-1A-0A') {
        throw 'Server did not return a PNG screenshot.'
    }
    $width = [Net.IPAddress]::NetworkToHostOrder([BitConverter]::ToInt32($bytes, 16))
    $height = [Net.IPAddress]::NetworkToHostOrder([BitConverter]::ToInt32($bytes, 20))
    if ($width -ne $screen.size.width -or $height -ne $screen.size.height) {
        throw 'Screenshot geometry differs from reported desktop geometry.'
    }
    Write-Host 'PNG screenshot captured and geometry checked; image not saved or printed.'
}
Write-Host 'Local checks passed. Controller connectivity and application selectors still need testing.'
