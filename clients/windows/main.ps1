Param(
    [string]$ControllerBase = "http://172.16.162.172:6001",
    [string]$RingFile = "C:\BrowserUpdate\ring.txt",
    [string]$BrowserListFile = "C:\BrowserUpdate\browsers.txt",  # 内容例: chrome,edge
    [string]$AuthToken = "replace-with-random-client-token-32chars",
    [switch]$ForceUpdate
)

$ErrorActionPreference = "Stop"
function Get-Ring {
    if (Test-Path $RingFile) { (Get-Content $RingFile -Raw).Trim() } else { "stable" }
}
function Get-Browsers {
    if (Test-Path $BrowserListFile) {
        (Get-Content $BrowserListFile | ForEach-Object { $_.Trim().ToLower() }) | Where-Object { $_ -in @("chrome", "edge") }
    }
    else {
        @("chrome", "edge")
    }
}

$ring = Get-Ring
$browsers = Get-Browsers
$host = $env:COMPUTERNAME
$os = (Get-CimInstance Win32_OperatingSystem).Caption

foreach ($browser in $browsers) {

    $configUrl = "$ControllerBase/config/$browser/$ring.json"
    try {
        $cfg = Invoke-RestMethod -Uri $configUrl -TimeoutSec 15
    }
    catch {
        Write-Host "[$browser] Config fetch failed: $($_.Exception.Message)"
        continue
    }

    # レジストリ パス
    if ($browser -eq "chrome") {
        $key = "HKLM:\SOFTWARE\Policies\Google\Update"
        $exe = "${Env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    }
    elseif ($browser -eq "edge") {
        $key = "HKLM:\SOFTWARE\Policies\Microsoft\EdgeUpdate"
        $exe = "${Env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    }

    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    Set-ItemProperty -Path $key -Name "UpdateDefault" -Value 0 -Type DWord
    Set-ItemProperty -Path $key -Name "AutoUpdateCheckPeriodMinutes" -Value $cfg.policy.autoUpdateCheckMinutes -Type DWord

    if ([string]::IsNullOrEmpty($cfg.targetVersionPrefix)) {
        Remove-ItemProperty -Path $key -Name "TargetVersionPrefix" -ErrorAction SilentlyContinue
    }
    else {
        Set-ItemProperty -Path $key -Name "TargetVersionPrefix" -Value $cfg.targetVersionPrefix -Type String
    }

    if (-not (Test-Path $exe)) {
        $localVersion = "NotInstalled"
    }
    else {
        $localVersion = (Get-Item $exe).VersionInfo.ProductVersion
    }

    $status = "OK"
    if ($localVersion -eq "NotInstalled") {
        $status = "MISSING"
    }
    else {
        $localMajor = [int]($localVersion.Split(".")[0])
        $latestMajor = [int]$cfg.latestStableMajor
        if ($cfg.targetVersionPrefix) {
            $targetMajor = [int]($cfg.targetVersionPrefix.TrimEnd("."))
            if ($localMajor -ne $targetMajor) { $status = "BLOCKED_WAIT_PREFIX" }
        }
        if ($status -eq "OK") {
            try {
                if ([version]$localVersion -lt [version]$cfg.minVersion) { $status = "OUTDATED" }
                elseif ($latestMajor - $localMajor -ge 2) { $status = "WARNING" }
            }
            catch {}
        }
    }

    if ($ForceUpdate -and (Test-Path $exe)) {
        $updateExe = "${Env:ProgramFiles(x86)}\Google\Update\GoogleUpdate.exe"
        if ($browser -eq "edge") {
            $updateExe = "${Env:ProgramFiles(x86)}\Microsoft\EdgeUpdate\MicrosoftEdgeUpdate.exe"
        }
        if (Test-Path $updateExe) {
            Start-Process $updateExe -ArgumentList "/ua /installsource scheduler" -Wait -ErrorAction SilentlyContinue
        }
    }

    $body = @{
        browser  = $browser
        hostname = $host
        os       = $os
        ring     = $ring
        version  = $localVersion
        status   = $status
        details  = ""
    } | ConvertTo-Json -Depth 4

    try {
        Invoke-RestMethod -Uri "$ControllerBase/report" -Method Post -Body $body -ContentType "application/json" -Headers @{ "X-Auth-Token" = $AuthToken } | Out-Null
        Write-Host "[$browser] Reported: $localVersion Status=$status"
    }
    catch {
        Write-Host "[$browser] Report failed: $($_.Exception.Message)"
    }
}