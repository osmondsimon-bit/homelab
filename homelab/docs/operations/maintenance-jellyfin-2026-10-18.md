# Jellyfin upgrade — 2026-10-18

Purpose: record the authorised Jellyfin migration, verification evidence, retained rollback artifacts
and remaining operator acceptance. Current deployment facts belong in [PLAN.md](../../PLAN.md).

## Scope and migration review

The operator approved the production maintenance window and brief Jellyfin interruptions, and
explicitly waived the temporary test container. No test guest was created. The upgrade retained
Debian 12, existing LXC isolation, media mounts, iGPU mapping and network access boundaries.

Reviewed the [major-release migration guidance](https://jellyfin.org/posts/jellyfin-release-12.0/),
the [12.1 migration fixes](https://github.com/jellyfin/jellyfin/releases/tag/v12.1) and the
[12.2 release](https://github.com/jellyfin/jellyfin/releases/tag/v12.2). The refreshed apt preview
changed only `jellyfin`, `jellyfin-server` and `jellyfin-web` from `10.11.11+deb12` to `12.2+deb12`,
and replaced `jellyfin-ffmpeg7` with `jellyfin-ffmpeg8` `8.1.3-1-bookworm`. Those exact packages
were downloaded through the signed repository before interruption and installed without further
downloads. No external plugin DLLs were installed; the bundled plugins were reviewed.

## Safeguards and retained artifacts

Preflight found a healthy Apophis pool, approximately 14 GiB available host memory, approximately
15 GiB free guest rootfs space, mounted USB media and an online independent Tailscale router.
SQLite integrity and foreign-key checks passed. Both usernames were distinct ignoring case;
neither playback nor scheduled tasks were active. A private baseline recorded account/password
hash preservation, library counts and encoding settings without publishing credentials.

Stopped CT 120 for coherent checkpoints. On Apophis, retain:

- Final pre-install rootfs snapshot:
  `rpool/data/subvol-120-disk-0@jellyfin-pre12-final-20261018`.
- Private directory `/var/lib/vz/dump/jellyfin-upgrade-20261018-retry1/`, containing the full
  `vzdump-lxc-120-2026_10_18-*.tar.zst` image, its SHA-256 manifest, the final
  `jellyfin-data-config.tar` and checksum, `120.conf`, the private baseline and maintenance logs.
- Earlier pre-install snapshots `jellyfin-pre12-20261018` and `jellyfin-pre12-20261018-retry1`
  on the same rootfs dataset. The retry snapshot corresponds to the full image; the final
  snapshot/application archive were refreshed immediately before installation.
- The initial failed attempt's configuration/log directory
  `/var/lib/vz/dump/jellyfin-upgrade-20261018/`; it contains no successful full image.

The first image attempt failed because a restrictive temporary-file umask blocked the mapped
container user; production returned to service without package changes. Retrying with Proxmox's
normal temporary-file permissions succeeded. Artifact directories are private and retained files
are mode `0600`. Full image decompression, required database/config presence and exclusion of
media contents passed. Empty media mount directories are expected. The final application archive
compared equal to the stopped filesystem; its database passed integrity and foreign-key checks.
Jellyfin startup was masked after backup capture until installation completed, then unmasked.

These checks validate archive contents and consistency. **No booted restore or migration trial
was performed**, as explicitly requested by the operator. Same-host artifacts support migration
rollback, not host-loss recovery; no recurring backup policy changed. Retain them until operator
acceptance and separately authorised cleanup. Follow the [rollback runbook](runbooks.md#jellyfin-major-upgrades-and-rollback)
to restore packages and their matching database together.

## Verification

The running API reports `12.2.0`; the service is active and enabled, setup remains complete,
and `dpkg --audit` is clean. Both users, their identities and password hashes survived unchanged.
Both libraries retained two movies, five episodes and one series. SQLite integrity and foreign-key
checks passed after migration. VAAPI, hardware encoding, throttling and segment deletion settings
were preserved. All six bundled plugins are active.

Two-second synthetic H.264 encodes succeeded with both `h264_vaapi` and `h264_qsv`, running as
the Jellyfin user against the passed-through render device. All configured library paths were
present before the required full scan. The scan completed successfully in approximately eleven
seconds and retained the catalogue counts.

Seerr's own Jellyfin-user and library API endpoints each returned HTTP 200 with two records,
proving its live client still reaches Jellyfin. Its stored connection/key also reached the server
information and catalogue endpoints using the supported `Authorization` header; the
[Seerr client](https://github.com/seerr-team/seerr/blob/v3.5.0/server/api/jellyfin.ts) already uses
that header. Seerr's application status returned HTTP 200. Jellyfin's post-upgrade journal recorded
startup completion with no error/fatal messages or migration-failure signatures. The maintenance
collector refreshed successfully; Apophis retained more than 13 GiB available memory and a healthy
pool at the final sample.

Client playback acceptance remains operator work. A synthetic encode does not prove playback on
every client; hard-refresh the web client if it retains old assets.
