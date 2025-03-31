# InstallPythonAndFixTcl.ps1
# This script downloads the official Python installer from python.org,
# installs Python 3.11.9 silently (for the current user), and sets the TCL_LIBRARY
# environment variable so that the bundled Tcl/Tk version is correctly recognized.
# It then verifies the installation by reporting the installed Python version.

# --- Configuration ---
$pythonVersion = "3.11.9"
$pythonMajorMinor = "3.11"  # For registry key lookup
$installerFileName = "python-$pythonVersion-amd64.exe"
$pythonInstallerURL = "https://www.python.org/ftp/python/$pythonVersion/$installerFileName"
$tempInstallerPath = Join-Path $env:TEMP $installerFileName

# --- Download Installer ---
Write-Host "Checking for Python installer ($installerFileName) in TEMP folder..." -ForegroundColor Cyan
if (!(Test-Path $tempInstallerPath)) {
    Write-Host "Downloading Python $pythonVersion installer from $pythonInstallerURL..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $pythonInstallerURL -OutFile $tempInstallerPath -UseBasicParsing
        Write-Host "Download complete." -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to download the Python installer: $_"
        exit 1
    }
}
else {
    Write-Host "Installer already exists at: $tempInstallerPath" -ForegroundColor Green
}

# --- Install Python Silently ---
Write-Host "Starting silent installation of Python $pythonVersion..." -ForegroundColor Cyan
# For a current-user install with PATH prepended and Tcl/Tk included.
$installArgs = "/quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1"
try {
    $process = Start-Process -FilePath $tempInstallerPath -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) {
        Write-Error "Python installer exited with code $($process.ExitCode)."
        exit 1
    }
    else {
        Write-Host "Python $pythonVersion installed successfully." -ForegroundColor Green
    }
}
catch {
    Write-Error "An error occurred during installation: $_"
    exit 1
}

# --- Locate Installed Python Path via Registry ---
$regPath = "HKCU:\Software\Python\PythonCore\$pythonMajorMinor\InstallPath"
try {
    $regProps = Get-ItemProperty -Path $regPath -ErrorAction Stop
    # The registry key's ExecutablePath holds the full path to python.exe.
    $pythonInstallPath = Split-Path $regProps.ExecutablePath -Parent
    Write-Host "Python installation directory detected at: $pythonInstallPath" -ForegroundColor Green
}
catch {
    Write-Error "Could not locate the Python installation in the registry at $regPath. $_"
    exit 1
}

# --- Set TCL_LIBRARY Environment Variable ---
$tclDir = Join-Path $pythonInstallPath "tcl\tcl8.6"
if (!(Test-Path $tclDir)) {
    Write-Error "Expected Tcl/Tk directory not found at: $tclDir"
    exit 1
}
else {
    # Set TCL_LIBRARY permanently for the current user and update the current session.
    [Environment]::SetEnvironmentVariable("TCL_LIBRARY", $tclDir, "User")
    $env:TCL_LIBRARY = $tclDir
    Write-Host "TCL_LIBRARY environment variable set to: $tclDir" -ForegroundColor Green
}

# --- Verification ---
Write-Host "Verifying Python installation..."
try {
    $pythonVersionOutput = & "$pythonInstallPath\python.exe" --version
    Write-Host "Installed Python version: $pythonVersionOutput" -ForegroundColor Green
}
catch {
    Write-Error "Failed to execute Python for version verification: $_"
}

Write-Host ""
Write-Host "Installation complete. Please restart your terminal (or log out/in) to apply permanent environment variable changes." -ForegroundColor Cyan
Pause
