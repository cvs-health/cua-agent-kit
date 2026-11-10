# Windows VM setup

Windows automation has two parts: a remote Windows VM running the applications
and `computer_server`, and an external kit process running on your local machine
or in a Docker container. The kit process connects to `computer_server` to
request screenshots, send input, and execute workflow scripts on the VM.

Set up the Windows VM using the steps below.

## Before you start

- Have a Windows VM with the target application installed.
- Install Python on the VM, including `pip` and `venv`.
- Sign into the VM's desktop, for example through RDP or the Windows App, and
  keep it unlocked.
- Make sure your local machine can reach the VM's private IP and server port.

## 1. Copy the setup folder

Copy the **whole `windows-host/` folder** from this repository to the VM.
Alternatively, clone the repository on the VM and use that folder.

Open PowerShell on the VM as the user who will run the applications. Change into
the copied `windows-host/` folder. Run the following setup commands there.

| Script           | What it does                                                |
| ---------------- | ----------------------------------------------------------- |
| `install.ps1`    | Installs `computer_server` and pywinauto's dependencies     |
| `start.ps1`      | Starts `computer_server` in your signed-in desktop          |
| `doctor.ps1`     | Checks the installation and running server                  |
| `disconnect.ps1` | Disconnects RDP while keeping the Windows session signed in |

Keep `host-common.ps1` and the requirements files beside these scripts.
`host-common.ps1` contains shared helper functions; you do not run it yourself.

## 2. Install the dependencies

```powershell
.\install.ps1
```

If `python` does not point to the installation you want to use, give the script
its full path:

```powershell
.\install.ps1 -PythonExe 'C:\Path\To\Python\python.exe'
```

The script creates a separate Python environment at:

```text
%LOCALAPPDATA%\cua-agent-kit\host\venv
```

`%LOCALAPPDATA%` is the current Windows user's local application-data folder.
The environment contains both the server and native automation dependencies; you
do not need a separate pywinauto installation.

## 3. Start the server

Replace the placeholder with the VM's private IP:

```powershell
$env:WINDOWS_HOST = 'YOUR_VM_PRIVATE_IP'
$env:WINDOWS_PORT = '8000'
.\start.ps1
```

Keep this PowerShell window open. Ctrl+C stops the server.

The address tells the server where to listen. Without these settings it listens
on `127.0.0.1:8000`, which is reachable only from inside the VM. Your local
machine needs a reachable private address.

The server can control the desktop and run commands. Keep it on a protected
private network; these scripts do not configure firewall rules or
authentication.

`start.ps1` also ensures that Python scripts launched by the server use the
Python environment installed in step 2.

## Next: discover and run a workflow

With the server running, follow the
[Windows section of the README](../README.md#windows) for local configuration,
discovery, codification, and replay commands.

## Optional: disconnect RDP without signing out

Use this when you want to leave the VM running without keeping your RDP
connection open.

`disconnect.ps1` transfers your current RDP session to the Windows console with
`tscon`. It disconnects your viewer but leaves the session signed in.

On the VM, open PowerShell **as administrator, as the same Windows user**, and
change into `windows-host/`. Preview the operation:

```powershell
.\disconnect.ps1 -ServerAddress 'YOUR_VM_PRIVATE_IP' -Port 8000 -WhatIf
```

Then disconnect:

```powershell
.\disconnect.ps1 -ServerAddress 'YOUR_VM_PRIVATE_IP' -Port 8000
```

The script writes a log to:

```text
%LOCALAPPDATA%\cua-agent-kit\host\disconnect.log
```

Afterward, use your local machine to run a small discovery or replay and check
its screenshots. Screen resolution may change when the session moves from RDP to
the console. Start a fresh run after any resolution change.

This handoff still needs testing in your environment. It does not guarantee
operation through locks, reboots, or automatic session logouts.

## Troubleshooting

Open a **second PowerShell window** and change into the same setup folder:

```powershell
.\doctor.ps1 -ServerAddress 'YOUR_VM_PRIVATE_IP' -Port 8000
```

This checks that dependencies load, the server responds, its Python commands run
in the expected environment and Windows session, and it reports screen
dimensions. It does not test your application's selectors or connectivity from
your local machine.

To also check that the server can return a PNG screenshot:

```powershell
.\doctor.ps1 -ServerAddress 'YOUR_VM_PRIVATE_IP' -Port 8000 -Screenshot
```
