#!/usr/bin/env bash
# Read-only UniFi query helper — lets the operator/agent inspect UniFi (UDM) config + state
# for reviews and troubleshooting WITHOUT a UI. Uses a read-only local account (the same
# kind unpoller uses) against the UniFi OS controller API, cookie auth, GET only.
#
# Assumes it runs from the mgmt-vm. Credentials live ONLY in ~/.unifi-ro.env (gitignored;
# never committed — ADR-006). Create it (chmod 600) with:
#   UNIFI_URL=https://<gateway-ip>      # the UDM/Cloud Gateway, no trailing slash
#   UNIFI_USER=prometheus_user          # a VIEW-ONLY local UniFi account
#   UNIFI_PASS=...                       # that account's password
#   UNIFI_SITE=default                   # optional; UniFi site id (default: default)
#
# The session cookie is cached (chmod 600) and reused across calls, re-logging-in only on
# expiry — UniFi throttles rapid repeated logins, so DON'T log in per request. Pass several
# endpoints to fetch them all under one login.
#
# Usage:
#   bash unifi-query.sh <endpoint> [<endpoint> ...]   # GET /proxy/network/api/s/<site>/<ep>
#   bash unifi-query.sh --list                        # show common read-only endpoints
# Examples:
#   unifi-query.sh rest/networkconf rest/firewallrule stat/device   # one login, three fetches
#   unifi-query.sh stat/sta                                          # connected clients
# Output is JSON (piped through jq if available). GET-only + a view-only account = read-only.
set -euo pipefail

ENV_FILE="${UNIFI_ENV_FILE:-$HOME/.unifi-ro.env}"
COOKIE="${TMPDIR:-/tmp}/unifi-ro-cookie-$(id -u)"
BODY="$(mktemp)"; trap 'rm -f "$BODY"' EXIT

COMMON_ENDPOINTS="rest/firewallrule rest/firewallgroup rest/networkconf rest/portconf rest/wlanconf rest/routing rest/user stat/device stat/sta stat/health self"

if [[ "${1:-}" == "--list" ]]; then
  echo "Common read-only endpoints:"; printf '  %s\n' $COMMON_ENDPOINTS
  echo "Note: UDMs on the zone-based firewall expose 0 rest/firewallrule — use the UI/v2 API for policies."
  exit 0
fi
if [[ $# -lt 1 ]]; then
  echo "Usage: bash unifi-query.sh <endpoint> [<endpoint> ...] | --list   (see header)" >&2
  exit 2
fi

[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE — see script header." >&2; exit 1; }
# shellcheck disable=SC1090
source "$ENV_FILE"
: "${UNIFI_URL:?set UNIFI_URL in $ENV_FILE}"
: "${UNIFI_USER:?set UNIFI_USER in $ENV_FILE}"
: "${UNIFI_PASS:?set UNIFI_PASS in $ENV_FILE}"
SITE="${UNIFI_SITE:-default}"
UNIFI_URL="${UNIFI_URL%/}"

login() {
  local code
  code="$(curl -sk -o /dev/null -w '%{http_code}' -c "$COOKIE" \
    -X POST "$UNIFI_URL/api/auth/login" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$UNIFI_USER\",\"password\":\"$UNIFI_PASS\"}")"
  [[ "$code" == "200" ]] || { echo "UniFi login failed (HTTP $code) — check $ENV_FILE." >&2; exit 1; }
  chmod 600 "$COOKIE" 2>/dev/null || true
}

# GET an endpoint into $BODY; relogin + retry once on 401/empty cookie.
fetch() {
  local ep="$1" code
  [[ -s "$COOKIE" ]] || login
  code="$(curl -sk -b "$COOKIE" -o "$BODY" -w '%{http_code}' "$UNIFI_URL/proxy/network/api/s/$SITE/$ep")"
  if [[ "$code" == "401" || ! -s "$BODY" ]]; then
    login
    code="$(curl -sk -b "$COOKIE" -o "$BODY" -w '%{http_code}' "$UNIFI_URL/proxy/network/api/s/$SITE/$ep")"
  fi
  [[ "$code" == "200" ]] || echo "  (HTTP $code for $ep)" >&2
}

multi=$([[ $# -gt 1 ]] && echo 1 || echo 0)
for ep in "$@"; do
  fetch "$ep"
  [[ "$multi" == "1" ]] && echo "===== $ep ====="
  if command -v jq >/dev/null 2>&1; then jq . < "$BODY"; else cat "$BODY"; echo; fi
done
