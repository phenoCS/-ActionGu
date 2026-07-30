<#
    Task Cultivation Timer - One-click Launcher (launcher.ps1)
    ==========================================================
    Detects Python on the machine; if missing, automatically downloads and
    silently installs it (elevated, all-users; a UAC prompt appears on first run), then launches main.py.
    Copy this whole folder to any Windows PC and double-click the launcher .bat file.
    The user needs to install nothing manually.
    NOTE: This file is intentionally ASCII-only (no non-English characters) so it
    parses correctly under the system ANSI codepage on Chinese Windows.
#>

$ErrorActionPreference = 'Stop'

# Script directory (program folder; data.json will live here)
$PROJECT_DIR = $PSScriptRoot
if (-not $PROJECT_DIR) { $PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $PROJECT_DIR) { $PROJECT_DIR = (Get-Location).Path }

$MAIN_PY = Join-Path $PROJECT_DIR 'main.py'
# Log goes to %TEMP% so the program folder stays clean (no stray log in user dir)
$LOG_FILE = Join-Path $env:TEMP 'xiuxian-timer-launcher.log'

function Write-Log {
    param([string]$Message, [string]$Color = 'White')
    $ts = Get-Date -Format 'HH:mm:ss'
    $line = "[$ts] $Message"
    Write-Host "  $line" -ForegroundColor $Color
    try { Add-Content -Path $LOG_FILE -Value $line -ErrorAction SilentlyContinue } catch { }
}

# ============ Python detection logic (adapted from the v11 project) ============
function Find-PythonExecutable {
    $pythonLocations = @(
        # Python.org system-wide installs
        "$env:SystemDrive\Python39\python.exe",
        "$env:SystemDrive\Python310\python.exe",
        "$env:SystemDrive\Python311\python.exe",
        "$env:SystemDrive\Python312\python.exe",
        "$env:SystemDrive\Python313\python.exe",
        "$env:SystemRoot\python.exe",
        # Per-user installs
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        # Windows Store / App paths
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe",
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.exe"
    )

    function Test-RealPython($exePath) {
        if (-not (Test-Path $exePath)) { return $false }
        try {
            $info = & $exePath --version 2>&1
            return ($LASTEXITCODE -eq 0)
        } catch { return $false }
    }

    # 1) python / python3 resolvable from PATH
    foreach ($cmd in @('python', 'python3')) {
        try {
            $resolved = (Get-Command $cmd -ErrorAction SilentlyContinue).Source
            if ($resolved -and (Test-RealPython $resolved)) {
                return @{ Exe = $resolved; Type = 'python'; Version = $null }
            }
        } catch { }
    }

    # 2) Common absolute paths
    foreach ($loc in $pythonLocations) {
        if ($loc -and (Test-RealPython $loc)) {
            return @{ Exe = $loc; Type = 'python'; Version = $null }
        }
    }

    # 3) Registry probe (machine + user)
    $regRoots = @('HKLM:\SOFTWARE\Python\PythonCore', 'HKCU:\SOFTWARE\Python\PythonCore')
    foreach ($root in $regRoots) {
        if (-not (Test-Path $root)) { continue }
        $versions = Get-ChildItem -Path $root -ErrorAction SilentlyContinue
        foreach ($ver in $versions) {
            $installPath = (Get-ItemProperty -Path $ver.PSPath -Name 'InstallPath' -ErrorAction SilentlyContinue).InstallPath
            if ($installPath) {
                $candidate = Join-Path $installPath 'python.exe'
                if (Test-RealPython $candidate) {
                    return @{ Exe = $candidate; Type = 'python'; Version = $ver.PSChildName }
                }
            }
        }
    }

    # 4) conda environment
    try {
        $condaPath = (Get-Command conda -ErrorAction SilentlyContinue).Source
        if ($condaPath) {
            $base = Split-Path -Parent (Split-Path -Parent $condaPath)
            $candidate = Join-Path $base 'python.exe'
            if (Test-RealPython $candidate) {
                return @{ Exe = $candidate; Type = 'python'; Version = $null }
            }
        }
    } catch { }

    # 5) Windows py launcher (can pick a version)
    try {
        $py = (Get-Command py -ErrorAction SilentlyContinue).Source
        if ($py) {
            $info = & $py -3 --version 2>&1
            if ($LASTEXITCODE -eq 0) {
                return @{ Exe = $py; Type = 'py'; Version = $null }
            }
        }
    } catch { }

    return $null
}

# ============ Auto download and silent install (current user, no admin) ============
function Install-PythonIfMissing {
    $pyInstaller = Join-Path $env:TEMP 'python-3.12.7-amd64.exe'
    $localPy = Join-Path $PROJECT_DIR 'python-3.12.7-amd64.exe'
    $pyDownloaded = $false

    # Offline first: if the installer exe is already next to this script, use it
    if (Test-Path $localPy) {
        try {
            $bytes = [System.IO.File]::ReadAllBytes($localPy)
            if ($bytes.Length -gt 20MB -and $bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A) {
                Unblock-File -Path $localPy -ErrorAction SilentlyContinue
                $pyInstaller = $localPy
                $pyDownloaded = $true
                Write-Log '[INFO] Using local Python installer (offline mode)' 'Cyan'
            }
        } catch { }
    }

    # Several mirrors (CN + official), tried in order for higher success rate
    $pyUrls = @(
        'https://mirrors.huaweicloud.com/python/3.12.7/python-3.12.7-amd64.exe',
        'https://registry.npmmirror.com/-/binary/python/3.12.7/python-3.12.7-amd64.exe',
        'https://mirrors.tuna.tsinghua.edu.cn/python/3.12.7/python-3.12.7-amd64.exe',
        'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe'
    )

    if (-not $pyDownloaded) {
        foreach ($url in $pyUrls) {
            Write-Log "[INFO] Downloading Python 3.12.7: $url"
            try {
                $req = [System.Net.HttpWebRequest]::Create($url)
                $req.Timeout = 90000
                $req.ReadWriteTimeout = 180000
                $req.AllowAutoRedirect = $true
                $resp = $req.GetResponse()
                $totalBytes = $resp.ContentLength
                $respStream = $resp.GetResponseStream()
                $fs = [System.IO.File]::Create($pyInstaller)
                $buffer = New-Object byte[] 65536
                $downloaded = 0L
                $sw = [System.Diagnostics.Stopwatch]::StartNew()
                while (($read = $respStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $fs.Write($buffer, 0, $read)
                    $downloaded += $read
                    if ($sw.ElapsedMilliseconds -ge 500 -and $totalBytes -gt 0) {
                        $pct = [math]::Round($downloaded * 100 / $totalBytes)
                        Write-Host "`r  Download: $pct% ($([math]::Round($downloaded/1MB,0))MB / $([math]::Round($totalBytes/1MB,0))MB)   " -NoNewline
                        $sw.Restart()
                    }
                }
                $fs.Close(); $respStream.Close(); $resp.Close()
                Write-Host ''
                if ((Test-Path $pyInstaller) -and (Get-Item $pyInstaller).Length -gt 20MB) {
                    $pyDownloaded = $true
                    break
                }
            } catch {
                Write-Host ''
                Write-Log "[WARN] Download failed: $($_.Exception.Message)"
                Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue
            }
        }
    }

    if ($pyDownloaded) {
        # Install ALL USERS (machine-wide, needs admin) + add to PATH.
        # Mirrors the v11 FlashTap installer: it only works under 360 / strict
        # policies when run ELEVATED with InstallAllUsers=1. The launcher must be
        # started as administrator (the start .bat self-elevates via UAC).
        # A per-user (InstallAllUsers=0) non-elevated install gets blocked by 360
        # (msiexec) and returns Windows Installer error 1625.
        Write-Log '[INFO] Installing Python silently (all users, elevated, added to PATH)...' 'Cyan'
        try {
            Unblock-File -Path $pyInstaller -ErrorAction SilentlyContinue
            $pyProc = Start-Process -FilePath $pyInstaller -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_test=0' -Wait -PassThru
            $pyExitCode = if ($pyProc) { $pyProc.ExitCode } else { -1 }
            if ($pyExitCode -eq 0) {
                Write-Log '[OK] Python installed' 'Green'
                # Refresh PATH so the new python is usable immediately
                $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
                $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
                $env:Path = "$machinePath;$userPath"
                Start-Sleep -Seconds 2
            } else {
                Write-Log "[WARN] Python install returned non-zero exit code: $pyExitCode" 'Yellow'
            }
        } catch {
            Write-Log "[WARN] Python install exception: $($_.Exception.Message)" 'Yellow'
        }
        # Only remove the temp download; keep any offline copy next to the script
        if ($pyInstaller -ne $localPy) { Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue }
    } else {
        Write-Log '[ERROR] Python download failed, cannot start' 'Red'
        Write-Log '[INFO] Please install Python 3.10+ and add it to PATH, then retry' 'Yellow'
    }
}

# ============ Main flow ============
try {
    Write-Host ''
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host '      Task Cultivation Timer - Launcher' -ForegroundColor Cyan
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host ''

    if (-not (Test-Path $MAIN_PY)) {
        Write-Log '[ERROR] main.py not found (keep launcher and main.py in same folder)' 'Red'
        Read-Host 'Press Enter to exit'
        exit 1
    }

    $pyInfo = Find-PythonExecutable
    if (-not $pyInfo) {
        Write-Log '[INFO] No Python detected, starting auto-install...' 'Yellow'
        Install-PythonIfMissing
        $pyInfo = Find-PythonExecutable
    }

    if (-not $pyInfo) {
        Write-Log '[ERROR] Still no Python found, cannot start' 'Red'
        Read-Host 'Press Enter to exit'
        exit 1
    }

    Write-Log "[OK] Using Python: $($pyInfo.Exe)" 'Green'

    # Switch to the program folder so data.json lands in the right place
    Set-Location $PROJECT_DIR
    if ($pyInfo.Type -eq 'py') {
        & $pyInfo.Exe -3 $MAIN_PY
    } else {
        & $pyInfo.Exe -u $MAIN_PY
    }
    $ec = $LASTEXITCODE
    Write-Log "[INFO] Program exited, exit code: $ec"
} catch {
    Write-Log "[FATAL] $($_.Exception.Message)" 'Red'
    Read-Host 'Press Enter to exit'
}
