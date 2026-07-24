# Environment health diagnostic — 2026-07-24

This document records a read-only health review prompted by the 2026-07-22 Apophis DIMM failure
and associated ZFS corruption. It separates current evidence from documented assumptions and
preserves the physical-host checks that still require operator execution.

## Status and safety boundary

**Status:** phase 1 complete; live physical-host collection pending.

Completed:

- reviewed the Apophis corruption handover, current architecture, monitoring, backup, power, and
  continuity documentation;
- collected a read-only baseline from VM 100 `mgmt-vm`;
- compared the permanent monitoring rules with the failure modes seen on Apophis; and
- prepared a read-only collection bundle for Apophis, Carter, and Oneill.

Not performed:

- no scrub, SMART self-test, MemTest86 run, stress test, reboot, package change, service restart, or
  configuration change;
- no direct connection to a Proxmox host, because host access from the agent has not been confirmed;
- no reading or copying of secrets, private-repository contents, encryption keys, or
  `group_vars/all.yml`.

Do not treat this phase as a clean bill of health for the physical hosts. The final host assessment
depends on the operator-run evidence under [Physical-host collection](#physical-host-collection).

## Incident anchor

The original Lenovo 16 GB SO-DIMM in Apophis failed on 2026-07-22. The event coincided with 64 ZFS
checksum errors and permanent damage to objects in the VM 100 live disk and VM 118 replication
target. The failed DIMM is the leading cause hypothesis because multiple zvols were affected while
the NVMe reported no media/data-integrity errors, but the root cause remains unproven.

Recovery evidence recorded on 2026-07-23 is strong:

- the remaining aftermarket 16 GB DIMM passed two full MemTest86 passes;
- the Apophis NVMe passed an extended self-test with no failing LBA;
- the damaged VM 100 and VM 118 objects were replaced from known-good sources;
- the recovery scrub repaired `0B`, found zero errors, and left all pool/device counters at zero;
- a fresh encrypted VM 100 PBS backup completed; and
- post-recovery checks found no new memory, PCIe, NVMe, ZFS, or checksum evidence.

This supports continued cautious operation. It does not prove the removed DIMM was the sole fault
or eliminate the need to watch the storage path.

## Verified VM 100 baseline

Evidence collected on 2026-07-24:

| Check | Result | Assessment |
|---|---|---|
| Uptime/load | 20h 47m; load approximately 0.05 | Healthy |
| Memory | 9.6 GiB total; 8.5 GiB available; no swap used | Healthy |
| Root filesystem | 30 GiB ext4; 54% used | Healthy capacity |
| ext4 error counters | Root LV and `/boot` both report zero errors and no last-error time | Healthy |
| Kernel recurrence scan | No OOM, MCE, hardware error, PCIe fault, block I/O error, ext4 error, or storage-reset match | Healthy |
| Git working tree | Clean and aligned with the recorded tracking ref | Healthy |
| Git object check | No corrupt or missing object; unreachable/dangling objects only | Healthy |
| Failed services | `openipmi.service` only | Low-risk VM hygiene issue |

The restored VM's first boot reported that the previous system journal was corrupt or ended
uncleanly, then replaced it. This is consistent with VM 100 having been restored from the July 21
PBS image. No subsequent ext4 or block-I/O error was found, and both ext4 error counters remain
zero.

`openipmi.service` cannot find an IPMI interface because VM 100 is a QEMU guest. Its failure leaves
systemd in `degraded` state but is not evidence of failing physical hardware. The Debian SMART
collector likewise reports SMART unavailable for the virtual QEMU disk; physical-disk health must
be assessed on Apophis, not inside VM 100.

The VM's systemd timers for maintenance, filesystem trim/checking, and node-exporter collectors are
scheduled. The physical filesystem superblock could not be opened without root permission, so the
readable kernel ext4 counters and journal scan were used instead.

## Risk assessment

### High — off-site recovery remains incomplete

Oneill's single SSD holds the only PBS datastore and HA backup share. Loss of Oneill's disk, theft,
fire, or a whole-site electrical event can remove the local recovery history at the same time as
production. The off-box copy of the PBS encryption key was recorded as saved previously, but it was
not positively verified during the Apophis recovery.

The immediate preservation priority is to verify the existing off-box key without displaying it,
then define and implement the already-planned encrypted off-site “regret set”: VM 100, VM 118,
VM 127, HA native backups, and the credential-bearing private recovery repository. A restore drill
must prove the off-site path.

### High — permanent monitoring does not cover the observed failure class

The temporary Apophis recovery monitor checks ZFS health and counters, NVMe health, kernel hardware
events, and the 3 GiB memory guardrail, but its fixed schedule ends after 2026-07-26.

The permanent Prometheus rules cover target/guest availability, filesystem capacity, memory
pressure, PVE storage capacity, replication, backup freshness, and maintenance state. They do not
currently alert on:

- ZFS pool health or non-zero READ/WRITE/CKSUM counters;
- ZFS known-data-error state or stale/missing scrub evidence;
- NVMe critical warnings, media/data-integrity errors, unsafe shutdown growth, wear, or temperature;
- SMART being unavailable or a physical device becoming unhealthy; or
- recurring MCE/EDAC, PCIe AER, NVMe reset/timeout, or kernel hardware-error messages.

Collectors being installed is not enough if their important metrics have no rule. Persistent,
low-noise physical-storage and ZFS alerts should replace the expiring incident checker after live
metric names are verified on all three hosts.

### High until verified — live health of Carter and Oneill is undocumented

The repository contains a detailed current hardware gate for Apophis but no equivalent recent,
side-by-side SMART, ZFS, memory-error, thermal, failed-unit, and unexpected-shutdown baseline for
Carter and Oneill. Both use single-device ZFS and carry important recovery roles. The operator-run
collection below closes the evidence gap without changing them.

### Moderate — single-device ZFS detects corruption but cannot repair it

Apophis, Carter, and Oneill each use a single-device `rpool`. ZFS checksums can detect corruption,
but a scrub has no redundant block from which to repair damage. Replication and PBS reduce service
loss, but they do not turn any individual pool into self-healing storage. This is an accepted
architecture constraint that deserves explicit priority when storage is redesigned.

### Moderate — reset, watchdog, and hard-lock paths remain open

Apophis previously reached `reboot.target` but failed to start a new boot until a cold power cycle.
It also experienced an unexplained hard lock near the first Media USB collector run. Both Lenovo
hosts now have current firmware, but controlled warm-reboot validation remains pending and the
active watchdog is software-only. These tests require a maintenance decision and are deliberately
outside this read-only audit.

### Moderate until verified — graceful power continuity

The future-rack design says the rack UPS is reserved but not initially fitted and relies on a
SigEnergy whole-home battery whose transfer time and low-state-of-charge shutdown path still need
proof. Other infrastructure data labels hosts as UPS-backed. That describes intended design, not
verified current runtime protection.

Confirm the currently installed power path separately. Sudden loss is particularly relevant to
three single-device ZFS hosts; automatic power-on after AC loss restores availability but does not
provide a clean shutdown.

### Low — management-VM monitoring noise

VM 100's expected `openipmi` failure makes the VM appear degraded. Its SMART collector emits a
zero-valued “healthy” metric because SMART is unavailable on the QEMU disk. Any future SMART rules
must scope alerts to physical hosts/devices with SMART actually available, rather than treating VM
100's virtual disk as failed.

### Documentation reliability concern

`physical_infra/compute/hosts.yaml` still describes Apophis as 32 GB, Carter as a prospective third
cluster member, and old guest placement. `PLAN.md` is authoritative and current. The stale physical
inventory should not be used for operational decisions until reconciled in a separate, focused
change.

## Physical-host collection

Run the following from VM 100. It makes SSH connections and runs read-only commands as root; it
does not start tests, scrub pools, clear counters, or change configuration. Output may include
hardware serial numbers and should remain local—do not commit the raw files.

```bash
audit_dir="/tmp/homelab-health-20260724"
mkdir -p "$audit_dir"

for host in apophis carter oneill; do
  ssh "root@${host}" 'bash -s' >"${audit_dir}/${host}.txt" 2>&1 <<'HOST_AUDIT'
set -u

section() {
  printf '\n===== %s =====\n' "$1"
}

section identity
date --iso-8601=seconds
hostname
uname -a
pveversion
uptime
last -x reboot shutdown -n 20

section failed-units-and-timers
systemctl --failed --no-pager
systemctl list-timers --all --no-pager | grep -Eai 'zfs|scrub|smart|trim|watchdog' || true

section memory
free -h
vmstat 1 5
dmidecode --type memory | grep -E '^[[:space:]]+(Locator|Size|Type:|Speed|Manufacturer|Part Number|Configured Memory Speed):' || true
for counter in /sys/devices/system/edac/mc/mc*/ce_count /sys/devices/system/edac/mc/mc*/ue_count; do
  test -r "$counter" && printf '%s: %s\n' "$counter" "$(cat "$counter")"
done

section storage-layout
lsblk -e 7 -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,ROTA,MODEL
df -hT
zpool list
zpool status -v
zpool get health,size,alloc,free,capacity,fragmentation,autotrim rpool
zfs list -o name,used,avail,refer,mountpoint

section smart
smartctl --scan-open || true
while read -r device _; do
  test -n "${device:-}" || continue
  printf '\n--- %s ---\n' "$device"
  smartctl -H -A -l error -l selftest "$device" || true
done < <(smartctl --scan-open 2>/dev/null)

section temperatures
sensors -A 2>/dev/null || true

section kernel-hardware-events
journalctl -k --since '2026-07-22 00:00:00' --no-pager |
  grep -Eai 'checksum|corrupt|I/O error|buffer I/O|blk_update|hardware error|machine check|mce:|edac|aer:.*(error|fault)|pcie.*(error|fault)|nvme.*(reset|timeout|abort|error|fail)|zfs.*(error|fault|checksum|corrupt)|oom|out of memory|thermal|throttl|watchdog|hung task|soft lockup|hard lockup' || true

section network-error-counters
for interface in /sys/class/net/*; do
  name="${interface##*/}"
  printf '%s rx_errors=%s rx_dropped=%s tx_errors=%s tx_dropped=%s\n' \
    "$name" \
    "$(cat "$interface/statistics/rx_errors")" \
    "$(cat "$interface/statistics/rx_dropped")" \
    "$(cat "$interface/statistics/tx_errors")" \
    "$(cat "$interface/statistics/tx_dropped")"
done

section proxmox
pvecm status 2>&1 || true
pvesm status
pvesr status 2>&1 || true
qm list
pct list
HOST_AUDIT
done

printf 'Reports written under %s\n' "$audit_dir"
```

After it completes, report only that the three files exist; the diagnostic session can read and
summarize them locally without pasting their raw contents into chat.

## Interpretation gates

Escalate immediately and stop optional Apophis media workloads if any of these appear:

- a non-zero or increasing ZFS READ/WRITE/CKSUM counter;
- `DEGRADED`, `FAULTED`, `UNAVAIL`, or known data errors in any pool;
- an NVMe/SMART critical warning, failed health state, media/data-integrity error, or failed
  self-test;
- an uncorrectable EDAC count, MCE/hardware error, repeated PCIe AER fault, NVMe reset/timeout, or
  filesystem/block-I/O error; or
- repeated thermal throttling, hard/soft lockup, or watchdog events.

Do not clear counters or run another scrub before preserving and reviewing the evidence. A clean
result should be recorded as a dated baseline for all three hosts, then used to design persistent
alerts and an appropriate future self-test/scrub cadence.

## Recommended sequence after collection

1. Classify all three host reports and update this document with the exact evidence.
2. Positively verify the off-box PBS encryption-key copy without exposing the key.
3. Replace the temporary Apophis checker with permanent, metric-backed ZFS/NVMe/SMART alerting.
4. Decide the off-site regret-set destination and prove a restore from it.
5. Schedule the two Lenovo warm-reboot tests separately, one node at a time.
6. Confirm the actual power-continuity path and graceful low-power shutdown behavior.
7. Reconcile the stale physical-infrastructure inventory in its own focused change.
