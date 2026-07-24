# Environment health diagnostic — 2026-07-24

This document records a read-only health review prompted by the 2026-07-22 Apophis DIMM failure
and associated ZFS corruption. It separates current evidence from documented assumptions and
preserves the physical-host checks that still require operator execution.

## Status and safety boundary

**Status:** read-only baseline complete; no immediate hardware-failure evidence found.

Completed:

- reviewed the Apophis corruption handover, current architecture, monitoring, backup, power, and
  continuity documentation;
- collected a read-only baseline from VM 100 `mgmt-vm`;
- compared the permanent monitoring rules with the failure modes seen on Apophis; and
- collected and classified a read-only baseline from Apophis, Carter, and Oneill.

Not performed:

- no scrub, SMART self-test, MemTest86 run, stress test, reboot, package change, service restart, or
  configuration change;
- no direct connection to a Proxmox host, because host access from the agent has not been confirmed;
- no reading or copying of secrets, private-repository contents, encryption keys, or
  `group_vars/all.yml`.

This is a current read-only baseline, not a hardware guarantee. Carter and Oneill have no recorded
SMART self-test history, and memory stress testing requires an offline maintenance window.

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

## Physical-host results

Evidence was collected at approximately 15:04 AEST on 2026-07-24.

| Host | ZFS | Primary-disk health | Memory | Kernel recurrence scan |
|---|---|---|---|---|
| Apophis | `ONLINE`; zero READ/WRITE/CKSUM counters; no known data errors; recovery scrub found zero errors | NVMe passed; 7% used; 30 °C; zero media/data-integrity errors; extended and short tests passed | 5.0 GiB available; installed 16 GB Kingston module correctly identified | No new memory, PCIe, NVMe, ZFS, I/O, lockup, OOM, or thermal fault |
| Carter | `ONLINE`; zero READ/WRITE/CKSUM counters; no known data errors; July 12 scrub found zero errors | NVMe passed; 1% used; 37 °C; zero media/data-integrity errors; no self-test recorded | 16 GiB available; two 16 GB modules operating at 2400 MT/s; no ECC support | No matching hardware/storage recurrence |
| Oneill | `ONLINE`; zero READ/WRITE/CKSUM counters; no known data errors; July 12 scrub found zero errors | SATA SSD passed; zero reallocated, pending, offline-uncorrectable, CRC, program, or erase errors; no self-test recorded | 11 GiB available; EDAC correctable and uncorrectable counters both zero | No matching hardware/storage recurrence |

The Apophis USB Samsung T5 also reports passed SMART health, 27 °C, no logged errors, and zero
reallocated, uncorrectable, CRC, program, or erase failures. Its ext4 filesystem is mounted with
approximately 53% free.

Operational state was also healthy:

- all hosts run Proxmox VE 9.2.4 with kernel `7.0.14-5-pve`;
- Apophis and Carter report a two-vote, two-node, quorate cluster;
- replication jobs `118-0` and `200-0` are current with `FailCount 0` and `State OK`;
- PBS storage on Oneill is active and approximately 18% used;
- expected guests are running and capacity-tier guests remain deliberately stopped;
- all physical interfaces report zero receive and transmit errors; accumulated drop counters are
  not accompanied by link errors in this snapshot; and
- the only failed unit on each host is `openipmi.service`, expected on hardware without an exposed
  IPMI interface.

No escalation gate was crossed. Optional Apophis media workloads do not need to be stopped on the
basis of this evidence.

### New follow-ups from the live evidence

- **Oneill storage temperature:** its SATA SSD reported 54 °C, materially warmer than the Apophis
  internal NVMe (30 °C), Apophis USB SSD (27 °C), and Carter NVMe (37 °C). SMART still passes and
  reports no error indicators, so this is not a failure declaration. Establish a trend and inspect
  cooling/airflow before adding load.
- **Carter SMART collection:** `prometheus-node-exporter-smartmon.timer` showed no next or previous
  run while the same timer is active on Apophis and Oneill. Carter's disk is healthy in the manual
  read, but its ongoing SMART metric collection is not proven.
- **No scheduled ZFS scrub surfaced:** none of the three `systemctl list-timers --all` results
  showed a ZFS scrub timer. Carter and Oneill have clean July 12 scrub results and Apophis has its
  clean recovery scrub, but future cadence is not proven.
- **Thermal visibility is incomplete:** `sensors -A` produced no CPU/system sensor data on any host.
  The storage devices expose temperatures through SMART, but host thermals cannot currently be
  assessed or alerted from this evidence.
- **No self-test history on Carter or Oneill:** SMART health and error attributes are clean, but
  neither primary disk has a recorded short or extended self-test. Starting tests is intentionally
  outside this read-only pass and should be approved as a separate maintenance action.
- **Cumulative unsafe-shutdown counters need trends:** Apophis reports 218 and Carter 220 NVMe
  unsafe shutdowns. Neither disk reports media errors or a failed self-test. Record these as the
  baseline and alert on increases; the cumulative values alone do not date or explain the events.
- **Carter uses mixed memory modules:** its SK Hynix 2667 MT/s and Samsung 2400 MT/s modules are
  both configured at 2400 MT/s. There is no current error evidence, but a future offline MemTest86
  pass would provide stronger confidence after the Apophis incident.
- **ZFS autotrim is off:** all three pools report `autotrim=off`. This is not an immediate integrity
  fault, but the intended SSD trim policy should be reviewed separately; the generic filesystem
  `fstrim.timer` does not by itself prove ZFS pool trimming.

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

### Moderate — Carter and Oneill lack self-test and offline-memory depth

The current SMART attributes, ZFS state, kernel evidence, and Oneill EDAC counters are clean.
Neither primary disk has a recorded self-test, Carter's consumer memory exposes no ECC counters,
and neither host has a documented recent offline MemTest86 result. These are confidence gaps, not
current failure evidence.

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
  test -d "$interface/statistics" || continue
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

The 2026-07-24 collection completed and the raw reports remain local under
`/tmp/homelab-health-20260724/`. Do not commit them.

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

1. Positively verify the off-box PBS encryption-key copy without exposing the key.
2. Replace the temporary Apophis checker with permanent, metric-backed ZFS/NVMe/SMART alerting,
   including repair of Carter's inactive SMART collection.
3. Confirm or establish a scheduled ZFS scrub and SSD trim policy for all three pools.
4. Establish CPU/system thermal collection and trend Oneill's comparatively warm SSD.
5. Decide the off-site regret-set destination and prove a restore from it.
6. Consider short/extended SMART tests for Carter and Oneill, then an offline Carter MemTest86 pass,
   as separately approved maintenance work.
7. Schedule the two Lenovo warm-reboot tests separately, one node at a time.
8. Confirm the actual power-continuity path and graceful low-power shutdown behavior.
9. Reconcile the stale physical-infrastructure inventory in its own focused change.
