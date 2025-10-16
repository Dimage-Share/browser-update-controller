#!/usr/bin/env bash
# macOS クライアント (Chrome / Edge)
CONTROLLER_BASE="http://172.16.162.172:6001"
AUTH_TOKEN="replace-with-random-client-token-32chars"
RING_FILE="/usr/local/browser-update/ring.txt"
BROWSER_LIST_FILE="/usr/local/browser-update/browsers.txt"

ring="stable"
[ -f "$RING_FILE" ] && ring=$(tr -d '\r\n ' < "$RING_FILE")
browsers="chrome edge"
[ -f "$BROWSER_LIST_FILE" ] && browsers=$(grep -v '^#' "$BROWSER_LIST_FILE" | tr '\n' ' ')

hostname=$(scutil --get ComputerName)
os=$(sw_vers -productName)" "$(sw_vers -productVersion)

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
  latestStable=$(echo "$cfg" | /usr/bin/python3 -c 'import sys,json;print(json.load(sys.stdin)["latestStable"])')
  latestMajor=$(echo "$latestStable" | cut -d. -f1)
  targetPrefix=$(echo "$cfg" | /usr/bin/python3 -c 'import sys,json;print(json.load(sys.stdin)["targetVersionPrefix"])')
  minVersion=$(echo "$cfg" | /usr/bin/python3 -c 'import sys,json;print(json.load(sys.stdin)["minVersion"])')

  if [ "$b" = "chrome" ]; then
    plist="/Applications/Google Chrome.app/Contents/Info.plist"
  else
    plist="/Applications/Microsoft Edge.app/Contents/Info.plist"
  fi

  if [ -f "$plist" ]; then
    localVersion=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$plist" 2>/dev/null)
  else
    localVersion="NotInstalled"
  fi

  status="OK"
  if [ "$localVersion" = "NotInstalled" ]; then
    status="MISSING"
  else
    localMajor=$(echo "$localVersion" | cut -d. -f1)
    if [ -n "$targetPrefix" ] && [ "$localMajor" != "${targetPrefix%.}" ]; then
      status="BLOCKED_WAIT_PREFIX"
    fi
    if [ "$status" = "OK" ]; then
      if [ -n "$minVersion" ] && [ "$localVersion" \< "$minVersion" ]; then
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