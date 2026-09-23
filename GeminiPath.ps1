param(
    [ValidateSet('doctor', 'install', 'start', 'stop', 'status', 'ag-scan', 'ag-patch', 'ag-restore')]
    [string]$Action = 'doctor',
    [ValidateSet('split', 'fake')]
    [string]$Mode = 'split'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$vendor = Join-Path $root 'vendor'
$install = Join-Path $vendor 'goodbyedpi-0.2.2'
$binary = Join-Path $install 'x86_64\goodbyedpi.exe'
$sessionFile = Join-Path $vendor 'session.json'
$domainsFile = Join-Path $root 'domains.txt'
$releaseUrl = 'https://github.com/ValdikSS/GoodbyeDPI/releases/download/0.2.2/goodbyedpi-0.2.2.zip'
$releaseHash = '00A2F8B99CD817F8C7FC4C449033015F039D18AF213DE78CB66BF202277C0628'

function Assert-Windows {
    if (-not [Environment]::OSVersion.Platform.Equals([PlatformID]::Win32NT)) {
        throw 'This tool requires Windows.'
    }
    $processor = Get-CimInstance Win32_Processor | Select-Object -First 1
    if ($processor.Architecture -ne 9) {
        throw 'The pinned GoodbyeDPI binary requires x64 (AMD64) Windows.'
    }
}

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Start an elevated Command Prompt (Run as administrator), then run GeminiPath.cmd start.'
    }
}

function Get-Session {
    if (-not (Test-Path -LiteralPath $sessionFile)) { return $null }
    try {
        $session = Get-Content -LiteralPath $sessionFile -Raw | ConvertFrom-Json
        if (-not $session.pid -or -not $session.started) { return $null }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($session.pid)" -ErrorAction Stop
        if (-not $process) { return $null }
        if (-not [string]::Equals($process.ExecutablePath, $binary, [StringComparison]::OrdinalIgnoreCase)) {
            return $null
        }
        $started = ([DateTime]$process.CreationDate).ToUniversalTime()
        $recorded = [DateTime]::Parse($session.started).ToUniversalTime()
        if ([Math]::Abs(($started - $recorded).TotalSeconds) -gt 5) { return $null }
        return $session
    } catch {
        return $null
    }
}

function Test-Domains {
    if (-not (Test-Path -LiteralPath $domainsFile)) { throw 'domains.txt is missing.' }
    $hosts = @(Get-Content -LiteralPath $domainsFile | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    if ($hosts.Count -eq 0) { throw 'domains.txt is empty.' }
    foreach ($hostname in $hosts) {
        if ($hostname -cnotmatch '^(?=.{3,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$') {
            throw "Invalid hostname in domains.txt: $hostname"
        }
    }
    return $hosts
}

function Get-DnsResult([string]$hostname) {
    try {
        $pending = [Net.Dns]::BeginGetHostAddresses($hostname, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(4000)) { return 'timeout' }
        $addresses = [Net.Dns]::EndGetHostAddresses($pending)
        if ($addresses.Length -eq 0) { return 'empty' }
        return 'ok'
    } catch { return 'failed' }
}

function Get-TcpResult([string]$hostname) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect($hostname, 443, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(4000)) { return 'timeout' }
        $client.EndConnect($pending)
        return 'ok'
    } catch { return 'failed' }
    finally { $client.Close() }
}

function Get-HttpResult([string]$hostname) {
    $request = [Net.HttpWebRequest][Net.WebRequest]::Create("https://$hostname/")
    $request.Timeout = 6000
    $request.ReadWriteTimeout = 6000
    $request.AllowAutoRedirect = $false
    $request.Method = 'GET'
    $request.Proxy = $null
    $request.UserAgent = 'GeminiPath/1.0 network-diagnostic'
    try {
        $response = [Net.HttpWebResponse]$request.GetResponse()
        try { return "HTTP $([int]$response.StatusCode)" }
        finally { $response.Close() }
    } catch [Net.WebException] {
        if ($_.Exception.Response) {
            try { return "HTTP $([int]$_.Exception.Response.StatusCode)" }
            finally { $_.Exception.Response.Close() }
        }
        return $_.Exception.Status.ToString()
    } catch { return 'failed' }
}

function Invoke-Doctor {
    $hosts = @(Test-Domains)
    Write-Host 'Network check (HTTP 3xx/4xx still means the server is reachable):'
    Write-Host ('{0,-35} {1,-9} {2,-9} {3}' -f 'Hostname', 'DNS', 'TCP:443', 'HTTPS')
    foreach ($hostname in @('example.com') + $hosts) {
        $dns = Get-DnsResult $hostname
        if ($dns -ne 'ok') {
            $tcp = '-'
            $https = '-'
        } else {
            $tcp = Get-TcpResult $hostname
            $https = Get-HttpResult $hostname
        }
        Write-Host ('{0,-35} {1,-9} {2,-9} {3}' -f $hostname, $dns, $tcp, $https)
    }
    Write-Host 'HTTPS success does not prove that Gemini chats, CLI, or Antigravity are available to this account.'
    Write-Host 'HTTP 403/451 alone cannot identify the blocker; check the actual app/account error.'
}

function Install-Engine {
    if (Test-Path -LiteralPath $binary) {
        Write-Host "Already installed: $binary"
        return
    }
    if (-not (Test-Path -LiteralPath $vendor)) { New-Item -ItemType Directory -Path $vendor | Out-Null }
    $staging = Join-Path $vendor ([Guid]::NewGuid().ToString('N'))
    $archive = Join-Path $vendor ([Guid]::NewGuid().ToString('N') + '.zip')
    try {
        Write-Host "Downloading GoodbyeDPI 0.2.2 from $releaseUrl"
        Invoke-WebRequest -UseBasicParsing -Uri $releaseUrl -OutFile $archive
        $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
        if ($actual -ne $releaseHash) { throw "Archive SHA-256 mismatch: $actual" }
        Expand-Archive -LiteralPath $archive -DestinationPath $staging
        $unpacked = Join-Path $staging 'goodbyedpi-0.2.2'
        foreach ($file in @('x86_64\goodbyedpi.exe', 'x86_64\WinDivert.dll', 'x86_64\WinDivert64.sys')) {
            if (-not (Test-Path -LiteralPath (Join-Path $unpacked $file))) { throw "Incomplete archive: $file" }
        }
        if (Test-Path -LiteralPath $install) { throw 'Partial installation exists: remove vendor/goodbyedpi-0.2.2 and retry.' }
        Move-Item -LiteralPath $unpacked -Destination $install
        Write-Host "Installed and verified SHA-256: $actual"
    } finally {
        if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
        if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    }
}

function Start-Engine {
    Assert-Admin
    $hosts = @(Test-Domains)
    if (-not (Test-Path -LiteralPath $binary)) { throw 'Run GeminiPath.cmd install first.' }
    $existing = Get-Session
    if ($existing) { throw "Already running with PID $($existing.pid). Use GeminiPath.cmd stop first." }
    $arguments = @('-e', '2', '--reverse-frag', '--blacklist', ('"' + $domainsFile + '"'))
    if ($Mode -eq 'fake') { $arguments += @('--wrong-chksum', '--wrong-seq') }
    Write-Host "Starting $Mode mode for $($hosts.Count) hostnames; no system proxy/DNS settings changed."
    $process = Start-Process -FilePath $binary -ArgumentList $arguments -PassThru
    Start-Sleep -Seconds 2
    $process.Refresh()
    if ($process.HasExited) { throw "GoodbyeDPI exited immediately (code $($process.ExitCode)). Check the new console window." }
    $info = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)"
    $started = ([DateTime]$info.CreationDate).ToUniversalTime().ToString('o')
    @{ pid = $process.Id; started = $started; mode = $Mode } | ConvertTo-Json | Set-Content -LiteralPath $sessionFile -Encoding ASCII
    Write-Host "Running (PID $($process.Id)). Keep the engine window open. Run doctor again to compare."
    Write-Host 'To stop: GeminiPath.cmd stop, or close the engine window.'
}

function Stop-Engine {
    Assert-Admin
    $session = Get-Session
    if (-not $session) { Write-Host 'No active session owned by GeminiPath.'; return }
    Stop-Process -Id $session.pid -ErrorAction Stop
    Remove-Item -LiteralPath $sessionFile -Force
    Write-Host "Stopped PID $($session.pid)."
}

try {
    Assert-Windows
    switch ($Action) {
        doctor { Invoke-Doctor }
        install { Install-Engine }
        start { Start-Engine }
        stop { Stop-Engine }
        status {
            $session = Get-Session
            if ($session) { Write-Host "Running: PID $($session.pid), mode $($session.mode)" }
            else { Write-Host 'Not running.' }
        }
        { $_ -in @('ag-scan', 'ag-patch', 'ag-restore') } {
            $operation = $Action.Substring(3)
            & py -3 (Join-Path $root 'antigravity_patch.py') $operation
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
