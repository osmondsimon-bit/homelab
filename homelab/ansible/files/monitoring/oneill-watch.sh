#!/usr/bin/env bash
# Independently check Oneill from Apophis; requires curl, timeout, flock and root-owned environment/state.
set -euo pipefail
umask 077

: "${NTFY_URL:?missing private notification URL}"
: "${MONITORING_URL:?missing monitoring health URL}"
: "${DNS_IP:?missing Technitium address}"
STATE_DIR="${STATE_DIR:-/var/lib/oneill-watch}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
NOTIFY_PREFIX="${NOTIFY_PREFIX:-Homelab}"

# curl reads its private URL from stdin, never argv. Reject curl-config delimiters.
case "$NTFY_URL" in
  *$'\n'*|*$'\r'*|*'"'*|*'\'*) echo 'oneill-watch: invalid notification URL' >&2; exit 2 ;;
esac
[[ "$NTFY_URL" == https://* ]] || { echo 'oneill-watch: HTTPS required' >&2; exit 2; }

install -d -m 0700 "$STATE_DIR"
install -d -m 0755 "$TEXTFILE_DIR"
exec 9>"$STATE_DIR/lock"
flock -n 9 || exit 0

write_state() {
  printf '%s\n' "$2" > "$STATE_DIR/$1.new"
  mv "$STATE_DIR/$1.new" "$STATE_DIR/$1"
}

publish() {
  local title="$1" priority="$2" body="$3"
  local -a args=(--config - --fail --silent --show-error
    --connect-timeout 3 --max-time 10 --retry 1 --retry-delay 1 --retry-max-time 12
    --header "Title: $NOTIFY_PREFIX: $title" --header "Priority: $priority"
    --header 'Tags: computer' --data "$body")
  if printf 'url = "%s"\n' "$NTFY_URL" | curl "${args[@]}" >/dev/null 2>&1; then
    return 0
  fi
  # Bootstrap DoH by literal IP; both the resolver and ntfy TLS certificates stay verified.
  # This second attempt does not require Oneill, Technitium or the host's system resolver.
  printf 'url = "%s"\n' "$NTFY_URL" |
    curl "${args[@]}" --doh-url https://1.1.1.1/dns-query >/dev/null 2>&1
}

fail=""
curl --fail --silent --show-error --connect-timeout 3 --max-time 5 \
  "$MONITORING_URL" >/dev/null 2>&1 || fail='monitoring(:9090) '
timeout 3 bash -c 'exec 3<>"/dev/tcp/$1/53"' _ "$DNS_IP" >/dev/null 2>&1 \
  || fail+='technitium-DNS(:53) '

previous="$(cat "$STATE_DIR/failure" 2>/dev/null || true)"
last_notified="$(cat "$STATE_DIR/last-notified" 2>/dev/null || true)"
[[ "$last_notified" =~ ^[0-9]+$ ]] || last_notified=0
delivery="$(cat "$STATE_DIR/delivery" 2>/dev/null || true)"
[[ "$delivery" == 0 ]] || delivery=1
now="$(date +%s)"
status=0
probe=1

if [[ -n "$fail" ]]; then
  probe=0
  if [[ "$fail" != "$previous" ]]; then
    write_state failure "$fail"
    last_notified=0
    write_state last-notified 0
  fi
  if (( now - last_notified >= 1800 )); then
    if publish 'Oneill unavailable' urgent \
      "Oneill check failed from Apophis: $fail. Glance, backup destinations and the normal alert pipeline may be unavailable. Check Oneill power, console and network; verify missed backups after recovery."; then
      write_state last-notified "$now"
      delivery=1
      echo 'oneill-watch: outage notification accepted' >&2
    else
      delivery=0
      status=1
      echo 'oneill-watch: notification delivery failed; retrying at next check' >&2
    fi
  fi
elif [[ -n "$previous" ]]; then
  if publish 'Oneill recovered' default \
    'Oneill monitoring and Technitium DNS are reachable again from Apophis. Check Glance and backup freshness after recovery.'; then
    rm -f "$STATE_DIR/failure" "$STATE_DIR/last-notified"
    delivery=1
    echo 'oneill-watch: recovery notification accepted' >&2
  else
    delivery=0
    status=1
    echo 'oneill-watch: recovery delivery failed; retrying at next check' >&2
  fi
fi
write_state delivery "$delivery"

metrics="$(mktemp "$TEXTFILE_DIR/.oneill-watch.XXXXXX")"
trap 'rm -f "$metrics"' EXIT
cat > "$metrics" <<EOF
# TYPE homelab_oneill_watch_last_check_timestamp_seconds gauge
homelab_oneill_watch_last_check_timestamp_seconds{node="apophis"} $(date +%s)
# TYPE homelab_oneill_watch_probe_success gauge
homelab_oneill_watch_probe_success{node="apophis"} $probe
# TYPE homelab_oneill_watch_delivery_success gauge
homelab_oneill_watch_delivery_success{node="apophis"} $delivery
EOF
chmod 0644 "$metrics"
mv "$metrics" "$TEXTFILE_DIR/homelab_oneill_watch.prom"
exit "$status"
