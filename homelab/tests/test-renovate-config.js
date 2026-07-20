#!/usr/bin/env node
// Validate that every Docker image annotation in Ansible defaults is detected by Renovate's custom managers.
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "../..");
const config = JSON.parse(fs.readFileSync(path.join(repoRoot, "renovate.json"), "utf8"));
const defaults = fs.readFileSync(
  path.join(repoRoot, "homelab/ansible/inventory/group_vars/all.yml.example"),
  "utf8",
);

const matches = config.customManagers.flatMap((manager) =>
  manager.matchStrings.flatMap((pattern) => [...defaults.matchAll(new RegExp(pattern, "g"))]),
);
const dependencies = matches.map((match) => match.groups.depName).sort();
const expected = [
  "actualbudget/actual-server",
  "ghcr.io/seerr-team/seerr",
  "ghcr.io/thephaseless/byparr",
  "lscr.io/linuxserver/prowlarr",
  "qmcgaw/gluetun",
  "vaultwarden/server",
].sort();

if (JSON.stringify(dependencies) !== JSON.stringify(expected)) {
  throw new Error(`Renovate image detection mismatch: ${JSON.stringify(dependencies)}`);
}

console.log("PASS: Renovate detects all six pinned Docker images");
