# SPDX-FileCopyrightText: Copyright 2026 CVS Health and/or one of its affiliates
# SPDX-License-Identifier: Apache-2.0

#
# Shared local paths and REST diagnostics. Dot-source from the entrypoint scripts.
Set-StrictMode -Version Latest

function Get-CuaHostRoot {
    param([string]$InstallRoot)
    if ($InstallRoot) { return [IO.Path]::GetFullPath($InstallRoot) }
    return Join-Path $env:LOCALAPPDATA 'cua-agent-kit\host'
}

function Get-CuaPython {
    param([string]$InstallRoot)
    $root = Get-CuaHostRoot $InstallRoot
    $python = Join-Path $root 'venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Host Python not found at $python. Run install.ps1 first."
    }
    return $python
}

function Assert-CuaWindows {
    if ($env:OS -ne 'Windows_NT') { throw 'Run this script on the Windows host.' }
    if ([Diagnostics.Process]::GetCurrentProcess().SessionId -eq 0) {
        throw 'Run in the intended signed-in desktop session, not session 0.'
    }
}

function Assert-CuaAddress {
    param([string]$Address)
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($Address, [ref]$parsed) -or
        $parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) {
        throw 'Use an IPv4 bind address, for example 127.0.0.1 or the VM private IP.'
    }
}

function Invoke-CuaCommand {
    param([string]$Address, [int]$Port, [string]$Command, [hashtable]$Parameters = @{})
    $payload = @{ command = $Command; params = $Parameters } | ConvertTo-Json -Depth 6 -Compress
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://${Address}:$Port/cmd" `
        -Method Post -ContentType 'application/json' -Body $payload -TimeoutSec 15
    $body = $response.Content.Trim()
    if ($body.StartsWith('data: ')) { $body = $body.Substring(6).Trim() }
    $result = $body | ConvertFrom-Json
    if ($result.success -ne $true) { throw "CUA command '$Command' failed." }
    return $result
}
