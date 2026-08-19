# The tunnel to Jarvis, kept open across sleeps and drops.
#
# **Why this exists.** A bare `ssh -N -L` dies whenever the laptop sleeps, the network changes,
# or the far end hiccups — and it dies *silently*. The local port stays bound for a while, the
# health endpoint keeps answering, and every model call quietly falls back to the deterministic
# rendering. What a reader sees is not an error: it is the product behaving exactly as designed
# for a box that is not there, with "Language model - not used" on every answer.
#
# That happened three times in one day and cost a sweep, whose model-written count fell from 12
# of 31 to 5 without a single test failing.
#
# **The remote port is 6006, not 11434.** A rebuilt box comes up with OLLAMA_HOST=0.0.0.0:6006.
# Forwarding to 11434 opens the local listener and then refuses every connection through it, so
# `netstat` shows LISTENING while nothing works.

param(
    [string]$RemoteHost = "root@151.185.34.32",
    [int]$LocalPort     = 11500,
    [int]$RemotePort    = 6006,
    [int]$CheckSeconds  = 20
)

$ErrorActionPreference = "Continue"

function Test-Jarvis {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$LocalPort/api/tags" -TimeoutSec 5 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Stop-StaleTunnel {
    # Kill by command line rather than by port: a dead ssh can leave the socket bound, and the
    # PID in the TCP table may name a parent that no longer exists.
    Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "$LocalPort" } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }
}

function Start-Tunnel {
    Stop-StaleTunnel
    Start-Sleep -Seconds 2
    $sshArgs = @(
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", "ExitOnForwardFailure=yes",
        # Tight keepalives so a half-dead link is noticed in seconds rather than minutes. The
        # far end is a rented box on someone else's network; assume the path is unreliable.
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "-o", "TCPKeepAlive=yes",
        "-N", "-L", "${LocalPort}:127.0.0.1:${RemotePort}",
        $RemoteHost
    )
    Start-Process -FilePath "ssh" -ArgumentList $sshArgs -WindowStyle Hidden
    Start-Sleep -Seconds 6
}

Write-Output "Watching the Jarvis tunnel on :$LocalPort -> ${RemoteHost}:$RemotePort"
Write-Output "Checking every ${CheckSeconds}s. Ctrl-C to stop."

while ($true) {
    if (-not (Test-Jarvis)) {
        $when = Get-Date -Format "HH:mm:ss"
        Write-Output "[$when] tunnel down - reopening"
        Start-Tunnel
        if (Test-Jarvis) {
            Write-Output "[$when] back up"
        } else {
            # Do not spin: a box that is genuinely off will not come back in two seconds, and a
            # reconnect storm makes the SSH server drop us for longer.
            Write-Output "[$when] still down - the box may be off. Retrying in ${CheckSeconds}s"
        }
    }
    Start-Sleep -Seconds $CheckSeconds
}
