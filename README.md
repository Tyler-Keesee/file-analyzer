# Advanced Storage Space Analyzer

A Windows-oriented PyQt6 desktop project that analyzes disk space and file types. It includes optional scientific and cloud-provider libraries. Its full UI, storage scanning, and cloud integrations have not been independently verified.

## Windows 11 setup: copy-paste one PowerShell command at a time

**Use Python 3.11.** The original dependency pins combined NumPy 2 with older scikit-learn and pandas binary builds, making fresh installs unreliable. Python 3.14 has not been validated for the complete toolchain.

1. Install Git and the Python 3.11 Windows package:

```powershell
winget install --id Python.Python.3.11 --exact
```

2. Close and reopen PowerShell, then run the commands below **separately**:

```powershell
py -3.11 --version
```
```powershell
git clone https://github.com/Tyler-Keesee/file-analyzer.git
```
```powershell
Set-Location .\file-analyzer
```
```powershell
py -3.11 -m venv .venv
```
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
```powershell
.\.venv\Scripts\python.exe -m pip check
```
```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py
```
```powershell
.\.venv\Scripts\python.exe main.py
```

**What each step does:** `py -3.11` selects Python 3.11 without changing your system's default Python; `venv` creates isolated dependencies; `pip install -r` reads the actual requirements list; `pip check` checks dependency consistency; `compileall` checks syntax; `main.py` starts the GUI.

**Verification limits:** Automated Windows CI installs dependencies and checks imports/syntax. Actual directory scans, external cloud services, UI actions and performance still require manual verification. This project scans local files, so choose only directories you want it to inspect. Do not run as Administrator unless a specific documented feature requires elevated permission.

## Troubleshooting

- `py -3.11` not found: close/reopen PowerShell after installation; check `py --list`.
- No `.venv\Scripts\python.exe`: environment creation failed; inspect that command before continuing.
- Qt GUI errors: use an interactive Windows desktop, not a headless SSH session.
- Missing cloud credentials: some integrations are optional and cannot be configured by cloning GitHub code.
- Existing checkout: `git pull --ff-only`, then reinstall dependencies with the local venv interpreter.
