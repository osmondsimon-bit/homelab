#!/bin/bash
# net-isolation-watchdog — self-heal a node that is L2-isolated because ITS OWN NIC wedged
# (the 2026-07-10 e1000e "Hardware Unit Hang": kernel alive, host powered, NIC dead). Designed to
# NOT reboot on a broader gateway/switch outage. See docs/operations/runbooks.md + PLAN.md.
#
# Reboot requires ALL of: sustained isolation from gateway AND every peer · past post-boot grace ·
# not rate-limited · recovery ladder tried+failed · a confirmed NIC-side symptom (e1000e hang).
# Config (real IPs, gitignored deploy): /etc/net-watchdog.conf → GATEWAY, PEERS, [NIC], [DRY_RUN].
set -uo pipefail
CONF="${CONF:-/etc/net-watchdog.conf}"; [ -r "$CONF" ] && . "$CONF"
NIC="${NIC:-nic0}"; DRY_RUN="${DRY_RUN:-0}"
GRACE_SECS=300; RATE_LIMIT_SECS=7200; FAIL_THRESHOLD="${FAIL_THRESHOLD:-20}"   # 20 × 30s = 10 min
STAMP=/var/lib/net-watchdog/last-reboot; STATE=/run/net-watchdog.fails
mkdir -p "$(dirname "$STAMP")"
log(){ logger -t net-watchdog "$*"; }
reach(){ ping -c1 -W2 "$1" >/dev/null 2>&1; }

# 1) Can I reach the gateway OR any peer? (peer up ⇒ my link is fine ⇒ upstream problem, not me)
ok=0; reach "${GATEWAY:-}" && ok=1
for p in ${PEERS:-}; do reach "$p" && ok=1; done
if [ "$ok" = 1 ]; then rm -f "$STATE"; exit 0; fi

# 2) Isolated — is it sustained?
fails=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 )); echo "$fails" > "$STATE"
log "isolated (no gateway/peer) fail #$fails/$FAIL_THRESHOLD"
[ "$fails" -lt "$FAIL_THRESHOLD" ] && exit 0

# 3) Guards: post-boot grace + cross-boot rate limit
up=$(cut -d. -f1 /proc/uptime); [ "$up" -lt "$GRACE_SECS" ] && { log "within boot grace; skip"; exit 0; }
now=$(date +%s); last=$(cat "$STAMP" 2>/dev/null || echo 0)
[ $(( now - last )) -lt "$RATE_LIMIT_SECS" ] && { log "rate-limited ($(((now-last)/60))m since last); NOT rebooting"; exit 0; }

# 4) Confirm it's a NIC-side hang (NOT a switch outage): recent e1000e Hardware Unit Hang
if journalctl -k --since "-15min" 2>/dev/null | grep -q "Detected Hardware Unit Hang"; then
  nic_symptom="e1000e hang"
elif [ "$(cat /sys/class/net/$NIC/carrier 2>/dev/null)" = "0" ]; then
  nic_symptom=""   # carrier down alone is ambiguous (could be switch) → alert only, do NOT reboot
else
  nic_symptom=""
fi
if [ -z "$nic_symptom" ]; then
  log "sustained isolation but NO NIC-hang symptom (likely upstream/switch) → ALERT ONLY, not rebooting"; exit 0
fi

# 5) Recovery ladder — try once, then reboot
log "sustained isolation + $nic_symptom → recovery attempt (link bounce + ifreload)"
ip link set "$NIC" down; sleep 2; ip link set "$NIC" up; sleep 5; ifreload -a >/dev/null 2>&1 || true; sleep 8
if reach "${GATEWAY:-}"; then log "recovery restored connectivity; not rebooting"; rm -f "$STATE"; exit 0; fi
for p in ${PEERS:-}; do reach "$p" && { log "recovery restored (peer); not rebooting"; rm -f "$STATE"; exit 0; }; done

# 6) Last resort
if [ "$DRY_RUN" = 1 ]; then log "DRY_RUN: WOULD reboot now ($nic_symptom)"; exit 0; fi
log "recovery failed; still isolated + $nic_symptom → REBOOTING (last resort)"; date +%s > "$STAMP"; sync; systemctl reboot || reboot -f
