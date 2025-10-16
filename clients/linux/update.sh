#!/usr/bin/env bash
# 簡易 Linux クライアント (Chrome / Edge) - Edge for Linux 利用の場合はパス調整
CONTROLLER_BASE="http://172.16.162.172:6001"
AUTH_TOKEN="replace-with-random-client-token-32chars"
RING_FILE="/opt/browser-update/ring.txt"
BROWSER_LIST_FILE="/opt/browser-update/browsers.txt"

ring="stable"
[ -f "$RING_FILE" ] && ring=$(tr -d '\r\n ' < "$RING_FILE")
browsers="chrome edge"
[ -f "$BROWSER_LIST_FILE" ] && browsers=$(grep -v '^#' "$BROWSER_LIST_FILE" | tr '\n' ' ')

hostname=$(hostname)
os="$(grep ^PRETTY_NAME= /etc/os-release | cut -d= -f2 | tr -d '\"')"

post_report () {
  local browser="$1" version="$2" status="$3"
  curl -s -X POST "$CONTROLLER_BASE/report" \
    -H "X-Auth-Token: $AUTH_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"browser\":\"$browser\",\"hostname\":\"$hostname\",\"os\":\"$os\",\"ring\":\"$ring\",\"version\":\"$version\",\"status\":\"$status\",\"details\":\"\"}" >/dev/null
}

for b in $browsers; do
  cfg=$(curl -s "$CONTROLLER_BASE/config/$b/$ring.json")
  [ -z "$cfg" ] && echo "[$b] config fetch failed" && continue
  latestStable=$(echo "$cfg" | jq -r '.latestStable')
  latestMajor=$(echo "$cfg" | jq -r '.latestStableMajor')
  targetPrefix=$(echo "$cfg" | jq -r '.targetVersionPrefix')
  minVersion=$(echo "$cfg" | jq -r '.minVersion')

  if [ "$b" = "chrome" ]; then
    ver_cmd="google-chrome --version 2>/dev/null | awk '{print \$3}'"
  else
    ver_cmd="microsoft-edge --version 2>/dev/null | awk '{print \$3}'"
  fi
  localVersion=$(bash -c "$ver_cmd")
  [ -z "$localVersion" ] && localVersion="NotInstalled"

  status="OK"
  if [ "$localVersion" = "NotInstalled" ]; then
    status="MISSING"
  else
    localMajor=$(echo "$localVersion" | cut -d. -f1)
    if [ -n "$targetPrefix" ] && [ "$localMajor" != "${targetPrefix%.}" ]; then
      status="BLOCKED_WAIT_PREFIX"
    fi
    if [ "$status" = "OK" ]; then
      # バージョン比較 (単純)
      if [ "$minVersion" != "" ] && [ "$localVersion" \< "$minVersion" ]; then
        status="OUTDATED"
      else
        diff=$((latestMajor - localMajor))
        [ $diff -ge 2 ] && status="WARNING"
      fi
    fi
  fi
  post_report "$b" "$localVersion" "$status"
  echo "[$b] version=$localVersion status=$status"
done