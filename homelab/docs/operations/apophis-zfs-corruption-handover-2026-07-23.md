# Apophis ZFS corruption recovery handover — 2026-07-23

This document hands an active Apophis storage-corruption incident from the primary management VM
(VM 100) to the independent recovery management VM (VM 128 on Carter). It records confirmed facts,
uncertainties, safety boundaries, and the next decision gates so a new AI session can continue
without relying on chat history.

## Current incident state

- Apophis `rpool` is a single-device ZFS-on-root pool and reports `ZFS-8000-8A`: permanent,
  unrecoverable data errors exist because no redundant copy is available on the pool.
- The affected objects reported by `zpool status -v` are:
  - VM 100 `mgmt-vm` live system disk: `rpool/data/vm-100-disk-1`.
  - VM 118 `vaultwarden` Apophis replication target: `rpool/data/vm-118-disk-0`.
  - One VM 118 replication snapshot on that target.
- ZFS reported 64 checksum errors on the NVMe pool device. A scrub completed on 2026-07-22,
  repaired `0B`, and reported six errors.
- The pool and device still show `ONLINE`. That means the device remains accessible; it does not
  mean the affected data is intact.
- No destructive recovery action has been performed by the agent. In particular:
  - no further scrub;
  - no `zpool clear`;
  - no deletion of affected datasets or snapshots;
  - no VM 100 migration, shutdown, restore, or replacement;
  - no VM 118 replication-target recreation;
  - no Apophis pool or host rebuild.
- The operator chose to stop the original session and continue from VM 128. Do not assume VM 100,
  VM 128, Apophis, or any replication job is in the same runtime state when the recovery session
  starts. Re-check live state before proposing changes.

### Recovery-session baseline verified from VM 128

Read-only checks at approximately 2026-07-23 16:22 local cluster time established:

- VM 128 `mgmt-vm2` is running on Carter with `onboot=0`, protection enabled, and its recovery
  tags intact. Its checkout was clean at `d36e481` on `agent/ai-ready-secondary-mgmt`, exactly
  synchronized with the remote branch.
- The two-node cluster is quorate with both votes present and expected votes unchanged at two.
- VM 100 is stopped on Apophis as deliberately arranged by the operator after the handover push.
  Its configuration still has `onboot=1`; no protection flag was reported.
- VMs 118 and 200 are running on Carter. Their Carter-to-Apophis replication jobs were enabled,
  current, and reported `State OK` with `FailCount 0`. This is status evidence only: the known
  corrupt VM 118 target on Apophis remains untrusted.
- The five capacity-tier media guests had been deliberately started after the incident. With
  operator approval, CTs 120, 121, 123, and 124 plus VM 125 were shut down again during recovery
  to reduce activity on the untrusted pool.
- PBS storage `pbs-oneill` was active. VM 100 restore points were visible through
  `2026-07-21T16:30:01Z`, which remains the newest known-good candidate. Carter had sufficient
  free ZFS capacity for an isolated 64 GB restore, and temporary VMID 198 was confirmed unused.
- VM 128 successfully administered Carter, Apophis, and Oneill.
- Apophis still reported the same `ZFS-8000-8A` permanent errors, 64 device checksum errors, and
  the same affected VM 100 and VM 118 objects. No errors were cleared and no additional scrub ran.
- The currently installed single 16 GB DIMM completed two full MemTest86 passes with zero errors.
  Apophis reported 6.7 GiB memory available after the media guests stopped.
- Current NVMe SMART health remained `PASSED`, with no critical warning, 7% used, and zero media
  and data-integrity errors. The extended NVMe self-test subsequently completed without error and
  reported no failing LBA. Review of the current boot found no machine-check, EDAC memory error,
  PCIe AER fault, NVMe reset/timeout/abort, or new ZFS fault. This passes the hardware-confidence
  gate for continued recovery but does not prove that the removed DIMM caused the corruption.

The newest known-good VM 100 candidate, `2026-07-21T16:30:01Z`, was restored to temporary VMID
198 on Carter in 49 seconds. Every virtual NIC was removed before first boot; the VM was set to
`onboot=0`, protected, and named `mgmt-vm-restore-test`. The guest booted, its filesystem and
normal Git history were readable and internally consistent, its working tree was clean, and the
required local-only Ansible inventory existed without displaying its contents. A zero-valued
Codex checkpoint ref made an unfiltered `git fsck` exit nonzero, but all objects reachable from
normal branch, remote, and tag refs were present. VM 198 remains running, isolated, and protected
as the validated safety copy.

Narrow-repair stage 1 completed successfully: the stopped VM 100 configuration and all VM 100
storage on Apophis were destroyed without `--purge`, preserving scheduled-backup selection. The
proven `2026-07-21T16:30:01Z` image restored to production VMID 100 on `local-zfs`; its EFI disk
was normalized by Proxmox, `onboot` was temporarily set to zero, and the guest started. The guest
agent responded and verified the expected hostname, readable filesystem, public repository, and
required local-only Ansible inventory. VM 198 remains the protected, no-network safety copy. ZFS
errors have not been cleared and no recovery scrub has run.

Narrow-repair stage 2 completed successfully: replication job `118-0` was disabled and deleted
with forced configuration-only cleanup, then only `rpool/data/vm-118-disk-0` and its snapshots were
destroyed on Apophis. The job was recreated from authoritative, running VM 118 on Carter; its first
run completed as a full send in approximately 77 seconds with `State OK` and `FailCount 0`. Job
`200-0` remained enabled and healthy throughout. ZFS errors still have not been cleared and no
recovery scrub has run.

Narrow-repair stage 3 completed successfully: after replacement, both VM 100 and VM 118 datasets
existed, VM 118 had a fresh replication snapshot, and `zpool status -v` reported no known data
errors. The historical counters were cleared once and a single recovery scrub completed in 28
seconds, repaired `0B`, and found zero errors. Final pool and device READ, WRITE, and CKSUM counters
were all zero, with `rpool` online and no known data errors. No additional scrub is required.

Narrow-repair stage 4 completed successfully: a fresh encrypted snapshot-mode PBS backup of running
VM 100 transferred the full 64 GiB virtual disk in 54 seconds, reported 77% sparse data, and
finished without an I/O error. PBS listed the new restore point as `2026-07-23T07:29:49Z` while
retaining the validated `2026-07-21T16:30:01Z` recovery point.

Preservation status reported by the operator:

- the sanctioned private local-config backup was run and pushed after the last meaningful change;
- no irreplaceable VM 100 data exists outside the public repository, private recovery repository,
  and PBS image;
- the public handover branch is synchronized;
- the off-box PBS encryption-key copy was **not positively verified**. After the successful isolated
  restore proved that Carter retained a working cluster-held key, the operator explicitly accepted
  the residual whole-cluster-loss risk and waived this verification gate; the copy must not be
  described as verified.
- the operator initially approved a full Apophis pool/host rebuild after the isolated restore
  passed, but paused before the cutoff command and requested a necessity review. No host shutdown,
  quorum change, node removal, or pool rebuild occurred.
- after reviewing the localized scrub findings, clean RAM/NVMe gates, proven VM 100 restore, and the
  additional operational risk of cluster removal and guest reprovisioning, the operator superseded
  the full-rebuild approval with explicit approval for a narrow repair. The approved scope is VM
  100 replacement from PBS plus full recreation of only VM 118's Apophis replication target,
  followed by a cleared error baseline, a zero-error scrub, and a verified fresh VM 100 backup. A
  full rebuild remains the fallback if errors recur.

## How the incident was detected

The scheduled PBS backup job is enabled and correctly selects VMs `100,118,127`, targets
`pbs-oneill`, and runs daily at `02:30` in snapshot mode with daily/weekly retention.

VM 100's 2026-07-23 02:30 AEST backup failed at about 28%:

```text
ERROR: job failed with err -5 - Input/output error
ERROR: Backup of VM 100 failed - job failed with err -5 - Input/output error
```

The failed job had successfully contacted PBS, enabled client-side encryption, frozen and thawed
the guest filesystem, and transferred data before QEMU returned `EIO`.

The last listed successful VM 100 restore point is:

```text
pbs-oneill:backup/vm/100/2026-07-21T16:30:01Z
```

That UTC timestamp corresponds to the scheduled 2026-07-22 02:30 AEST run. Treat it as the newest
known-good candidate, not as proven restorable, until an isolated restore validates it.

## What is known to remain healthy

- PBS accepted fresh VM 118 and VM 127 backups from Carter at approximately
  `2026-07-22T16:30Z`. This strongly isolates the failed VM 100 job from the PBS datastore and
  general backup network path.
- VM 118's authoritative running disk is on Carter. The corrupted object on Apophis is its
  replication target, not the authoritative source.
- VM 200's replication receiver continued writing snapshots on Apophis after the incident. This
  confirms activity, not end-to-end integrity; it does not make the current pool trustworthy.
- The repository branch `agent/ai-ready-secondary-mgmt` was clean and synchronized with its remote
  before this handover document was added.
- VM 128 `mgmt-vm2` is documented as a validated, cold, independent recovery control node on
  Carter. It is not a VM 100 clone and must not receive copied agent authentication or machine
  identity from VM 100.

## Hardware evidence and uncertainty

The Apophis NVMe SMART report showed:

- overall health: `PASSED`;
- critical warning: none;
- available spare: 100%;
- percentage used: 7%;
- media and data-integrity errors: 0;
- normal reported temperature;
- the latest short self-test completed without error.

The NVMe error log contains `Invalid Field in Command` entries, not failed-media LBAs. This SMART
evidence does not implicate the NAND directly, but SMART cannot prove that the entire storage path
is sound.

Apophis also had a DIMM failure on 2026-07-22. A later replacement DIMM is recorded in `PLAN.md` as
healthy. Because checksum damage appeared across more than one zvol while NVMe media errors remain
zero, the failed DIMM is the leading cause hypothesis. It is not proven. Before reusing the current
NVMe or trusting a rebuilt pool, establish:

1. whether the currently installed DIMM completed an offline MemTest86 pass;
2. whether an extended NVMe self-test completes without error;
3. whether new kernel, PCIe, NVMe, or ZFS errors appear after the hardware change.

Do not replace the NVMe solely because `zpool status` lists checksum damage. Conversely, do not
reuse it solely because SMART says `PASSED`.

## Recovery safety boundaries

- Do not print or copy values from `group_vars/all.yml`, the PBS encryption key, private Git
  repositories, SSH private keys, or agent authentication state.
- `/home/simon/homelab-private` is credential-bearing recovery material. Never use its nested
  `homelab/` snapshot as a working or deployment tree.
- Do not run another scrub, clear ZFS errors, retry VM 100's full backup, or attempt to migrate its
  damaged zvol before agreeing on a recovery plan.
- Do not assume replication will heal VM 118. An incremental send can leave an unchanged corrupted
  block in place; the Apophis target needs deliberate full recreation after the storage is trusted.
- Do not lower expected cluster votes while Apophis may still be running or during an uncertain
  network partition.
- Do not delete VM 100 or its zvol until a PBS restore has been completed and validated in
  isolation.
- Treat all destroy, pool recreation, node removal, restore-over-existing-ID, and replication
  recreation commands as destructive. Present exact targets and obtain explicit operator approval
  immediately before execution.

## Recovery-session priorities

### 1. Re-establish control without changing infrastructure

Start by reading:

- this handover;
- root `AGENTS.md`;
- `homelab/docs/operations/runbooks.md`, especially **Cold secondary management VM**,
  **Phase 4b: rebuild apophis on ZFS**, and the PBS restore section;
- `homelab/decisions/000-mgmt-vm.md`;
- `homelab/decisions/012-backups.md`;
- the current placement and incident notes in `homelab/PLAN.md`.

Then perform read-only checks of:

- current Git branch, cleanliness, and remote synchronization on VM 128;
- cluster quorum and node visibility;
- VM 100 and VM 128 power state;
- VM 118 and VM 200 placement;
- replication status;
- current `zpool status -v` on Apophis;
- available PBS restore points for VM 100;
- whether the local-only private config backup is current, without displaying its contents.

The repository says AI sessions cannot directly reach the private infrastructure unless access has
been explicitly confirmed. Ask the operator to run host commands when necessary.

### 2. Close preservation gates

Before taking VM 100 offline or changing the pool, explicitly verify:

- the public repository contains all intended VM 100 commits;
- the sanctioned `backup-local-config.sh` recovery copy is current;
- any irreplaceable VM 100 data outside the public and private repositories has an off-box copy;
- VM 128 can administer Carter, Apophis, and Oneill;
- the off-box PBS encryption key copy still exists;
- VM 100's latest known-good PBS image is visible from Carter.

Do not infer any of these from this handover; they were proposed but not confirmed in the original
session.

### 3. Establish hardware confidence

The pending non-destructive NVMe check is:

```bash
smartctl -t long /dev/nvme0n1
# After the duration reported by smartctl:
smartctl -l selftest /dev/nvme0n1
```

Memory validation requires an offline test and therefore a maintenance decision. Confirm which DIMM
is installed and whether it has already passed MemTest86 before scheduling another outage.

### 4. Validate recovery before destroying the damaged source

The conservative gate is an isolated restore of the newest known-good VM 100 PBS image onto
Carter using a temporary VMID and no production network identity. Validate at least:

- the guest boots;
- its expected filesystem is readable;
- the public repository exists and is internally consistent;
- the required local-only Ansible inventory exists, without displaying secrets;
- the restored guest does not conflict with the live VM 100 hostname, IP, MAC, or credentials.

Use the existing PBS restore-drill procedure as the starting point, but select a currently unused
temporary VMID and verify capacity first. Do not blindly reuse an old example VMID.

### 5. Choose the repair scope

The preferred safety-first option is a clean Apophis pool/host rebuild using the established
Phase 4b runbook, adapted because VM 100 cannot be migrated from its corrupted zvol:

1. validate the VM 100 PBS restore on Carter;
2. preserve cluster quorum and remove Apophis in the documented order;
3. recreate ZFS on a storage device that has passed the agreed hardware gates;
4. rejoin and provision Apophis;
5. restore VM 100 from PBS;
6. recreate VM 118 and VM 200 replication from their authoritative Carter sources;
7. rebuild reproducible Apophis guests as required;
8. run a clean scrub and require zero errors;
9. take and verify a fresh VM 100 PBS backup;
10. update the incident documentation with the proven root cause, recovery result, and restore
    evidence.

A narrower delete-and-restore of only the listed zvols may be technically possible if the hardware
is proven sound, but it leaves less confidence than recreating this small, single-device pool.
Present both options and their trade-offs before the operator chooses.

## Prompt for the recovery Codex session

Before launching Codex on VM 128, bring its checkout onto the handover branch:

```bash
cd ~/src/homelab
git status --short --branch
git fetch origin
git switch agent/ai-ready-secondary-mgmt
git pull --ff-only
```

Stop if the checkout has uncommitted changes or cannot fast-forward. Then paste this prompt:

```text
Continue the Apophis ZFS corruption recovery from VM 128 (mgmt-vm2).

First read the repository's root AGENTS.md and
homelab/docs/operations/apophis-zfs-corruption-handover-2026-07-23.md in full. Also read only the
directly referenced recovery sections and files identified by that handover.

Treat the handover as historical evidence, not current live state. Begin with a concise recovery
plan and read-only verification. Ask me to run commands on the private Proxmox infrastructure; do
not assume you can reach it. Do not print credentials, private configuration, encryption keys,
hardware serial numbers, or agent authentication.

Do not clear ZFS errors, scrub again, retry the VM 100 backup, migrate or delete VM 100, destroy
datasets, change quorum, recreate replication, or rebuild Apophis until the preservation gates and
an isolated VM 100 PBS restore are verified and I explicitly approve the destructive phase.

The goal is to preserve current recoverable state, establish whether the replacement RAM and NVMe
can be trusted, validate VM 100's latest known-good PBS image on Carter, then carry out the smallest
recovery plan that restores Apophis to a zero-error ZFS state. Keep the handover and PLAN/runbook
current as verified facts change, and commit and push focused documentation changes after each
completed recovery stage.
```
