# **AGENTS.md**

Defines how AI coding agents (OpenAI Codex, Claude Code, Cursor, etc.) should operate in this repository.
Supplements `README.md` (for humans) and nested `AGENTS.md` files (for scoped behavior).

---

## **PROJECT**

**Project Name:**
Simon's Homelab Infrastructure

**Description:**
Documentation, provisioning scripts, and configuration for a Proxmox-based home server (apophis). Single user, personal use, public GitHub repo. Tracks architecture decisions via ADRs, Ansible inventory, and Bash provisioning scripts for services running in VMs and LXCs.

**Technical Overview:**

* Core languages: Bash (scripts), YAML (Ansible/config), Markdown (docs/ADRs)
* CI/CD: None currently
* Deployment target: Proxmox VE on apophis (YOUR_PROXMOX_IP); services run in VMs and LXCs
* Hosting: Self-hosted, local network only — Tailscale for remote access, Cloudflare Tunnel for Home Assistant

---

## **GUIDELINES**

### **Core Principles**

1. **Keep it modular and simple.**

   * Small, focused functions/files; minimal deps; readability first. Leave room for future expansion.

2. **Preserve existing functionality.**

   * Modify only when directed; additive or reparative work.
   * Guard against regressions; validate existing behavior.
   * Lean on regression tests to prevent drift; extend coverage for critical paths.

3. **Mobile-first and observable.**

   * Design mobile-first, verify desktop.
   * Ship a favicon in the HTML head.
   * Surface build/version in the UI and keep it in sync with release metadata.

4. **Log from day one.**

   * Structured, meaningful logging for errors/warnings/key actions from the start.
   * If appropriate, put a page to see logs in the UI.
   * Create a logging endpoint you (the AI agent) can use to retrieve logs for debugging.

5. **Refine in passes.**

   * Multiple passes for quality/readability; flag non-standard patterns and suggest standardization/accessibility for AI readability.

6. **Maintain documentation and context.**

   * Each file starts with a short overview.
   * Keep `README.md`, nested `AGENTS.md`, and `TODO`/`notes.md` current.
    * **At any point, I should be able to start a new AI conversation and not lose context.**

7. **Ask questions early.**

   * Don't guess; request clarification early.

8. **Plan first, code second.**

   * Outline steps and confirm before coding.

9. **Limit sprawl and keep commits focused.**

   * Keep PRs atomic and on-topic.

10. **Use red / green test-driven development.**

    * Write and run tests *before* coding; ensure coverage for new changes. Protect new features with thorough regression tests and add any other type of tests necessary for stable, production deployments.

11. **Use AI-readable structure.**

    * Clear directories, consistent naming, and Markdown/YAML configs.

---

### **Git & Commit Rules**

* IMPORTANT: You - the AI agent - handle commits and syncs after you finish every task.
* Follow **Chris Beams' commit style** (&#91;https://cbea.ms/git-commit](https://cbea.ms/git-commit)):

  * Imperative mood ("Add feature X").
  * Explain *what* and *why* in the body.

**Example:**

```
feat(auth): add Azure AD token caching

Ensures cached tokens are reused across requests to reduce latency.
Follows Microsoft's best practice for cloud API throttling.
```

---

### **General Notes**

* No emojis in code, logs, or terminal output.
* Minimal dependencies; use standard libraries when possible.
* Verify licenses before adding external packages.
* Other than the Project section, do not update Agents.md. It must stay short so critical rules can be remembered. Create other documentation files when needed.

---

## **OPTIONAL CONTEXT**

### **Homelab Projects**

* Developed in **VSCode** using **Claude Code** (admin VM: Ubuntu Server, YOUR_MGMT_VM_IP).
* Hypervisor: **Proxmox VE** on apophis (YOUR_PROXMOX_IP, Intel i7-8700T, 16 GB RAM). Services run as **VMs or LXCs** — not Docker containers. See `homelab/PLAN.md` for service inventory and RAM budget.
* The AI agent cannot reach the Proxmox host or any VM/LXC directly — they are on a private network. SSH commands must be run by the user unless Tailscale is confirmed active.
* Remote access: **Cloudflare Tunnel** (Home Assistant only) + **Tailscale** (admin/SSH, Phase 2). No ports forwarded from the internet.
* Homelab is available on local network only. Tailscale provides remote access once deployed.
* Preferred stack for future app projects: Python, Flask and / or FastAPI, Pico.css (add to repo, not from CDN), SQLite. Bootstrap icons (or Phosphor icons as backup) — import to project, don't load from CDN. No emojis in UI.
* Source control: **GitHub** — github.com/osmondsimon-bit/homelab.

---

## **FOR LATER PASSES**

Schedule refinement passes for:

* Conciseness and readability
* Simplicity and modularity
* Error handling, logging, and static analysis
* Broader test coverage
* CAREFULLY clean up outdated or unused files
* security review
