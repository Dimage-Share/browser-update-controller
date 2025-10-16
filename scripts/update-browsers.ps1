<#!
.SYNOPSIS
  Chrome / Edge をローカル端末でサイレント更新するスクリプト。
.DESCRIPTION
  - API (browser-update-controller) から最新バージョンを取得し、ローカルと差分があれば更新。
  - Chrome: 現在バージョンをレジストリから参照。最新版 MSI をダウンロードしサイレントインストール。
  - Edge: winget を利用して upgrade 実行。
.PARAMETER ControllerBaseUrl
  例: http://172.16.162.172:6001
#>
param(
    [string]$ControllerBaseUrl = "http://172.16.162.172:6001",
    [switch]$Force
)

$ProgressPreference = 'SilentlyContinue'

function Write-Log {
    param([string]$Level = 'INFO', [string]$Message)
    $ts = (Get-Date).ToString('s')
    Write-Output "[$ts] [$Level] $Message"
}

function Get-LocalChromeVersion {
    try {
        $paths = @(
            'HKLM:SOFTWARE\\Google\\Chrome\\BLBeacon',
            'HKLM:SOFTWARE\\WOW6432Node\\Google\\Chrome\\BLBeacon'
        )
        foreach ($p in $paths) {
            if (Test-Path $p) {
                $v = (Get-ItemProperty -Path $p -Name version -ErrorAction Stop).version
                if ($v) { return $v }
            }
        }
    }
    catch {}
    return $null
}

function Get-LatestVersionsFromController {
    param([string]$BaseUrl)
    try {
        $resp = Invoke-RestMethod -Uri "$BaseUrl/versions" -Method GET -TimeoutSec 20
        return $resp
    }
    catch {
        Write-Log 'ERROR' "コントローラからバージョン取得失敗: $($_.Exception.Message)"
        return $null
    }
}

function Install-LatestChrome {
    param([string]$LatestVersion)
    $temp = Join-Path $env:TEMP "chrome_enterprise.msi"
    $downloadUrl = 'https://dl.google.com/tag/s/appguid%3D%7B8A69D345-D564-463C-AFF1-A69D9E530F96%7D%26iid%3D%7B00000000-0000-0000-0000-000000000000%7D%26lang%3Den%26browser%3D4%26usagestats%3D0%26appname%3DGoogle%2520Chrome%26needsadmin%3Dprefers/edgedl/chrome/install/GoogleChromeEnterpriseBundle64.msi'
    try {
        Write-Log 'INFO' "Chrome MSI ダウンロード: $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $temp -UseBasicParsing
        Write-Log 'INFO' 'Chrome インストール開始 (サイレント)'
        $args = "/i `"$temp`" /qn /norestart"
        $proc = Start-Process msiexec.exe -ArgumentList $args -Wait -PassThru
        if ($proc.ExitCode -eq 0) {
            Write-Log 'INFO' 'Chrome インストール完了'
        }
        else {
            Write-Log 'ERROR' "Chrome インストーラ終了コード: $($proc.ExitCode)"
        }
    }
    catch {
        Write-Log 'ERROR' "Chrome インストール失敗: $($_.Exception.Message)"
    }
    finally {
        if (Test-Path $temp) { Remove-Item $temp -Force }
    }
}

function Update-Edge {
    try {
        Write-Log 'INFO' 'Edge 更新実行 (winget)'
        winget upgrade --id Microsoft.Edge -e --silent | Out-Null
    }
    catch {
        Write-Log 'ERROR' "Edge 更新失敗: $($_.Exception.Message)"
    }
}

# Main
$versions = Get-LatestVersionsFromController -BaseUrl $ControllerBaseUrl
if (-not $versions) {
    Write-Log 'WARN' 'コントローラが利用できないため、Edge のみ winget で更新を試行'
    Update-Edge
    exit 0
}

$latestChrome = $versions.chrome.version
$localChrome = Get-LocalChromeVersion
Write-Log 'INFO' "Local Chrome: $localChrome / Latest: $latestChrome"
if ($Force -or -not $localChrome -or ($latestChrome -and $localChrome -ne $latestChrome)) {
    Install-LatestChrome -LatestVersion $latestChrome
}
else {
    Write-Log 'INFO' 'Chrome は最新またはバージョン不明のためスキップ'
}

Update-Edge

Write-Log 'INFO' '完了'
