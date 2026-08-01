# Actual Budget monthly AI insights

Manual category-only narrative overlay for Actual Budget on VM 127. The implementation is codified
but **disabled by default** until the operator stages its four local secret files, opts in, deploys,
and completes the live acceptance checks below.

| | |
|---|---|
| Placement | companion container in Actual VM 127 on Carter |
| URL | `https://actual.<tailnet>.ts.net/insights` |
| Trigger | operator clicks **Generate monthly memo** for a completed month |
| Schedule | none; no timer, cron, webhook, or background generation |
| Actual access | official `@actual-app/api` `26.7.0`; category budget reads only |
| Model | OpenAI Responses API, default `gpt-5.6-terra`, low reasoning, `store: false`, no tools |
| Model input | category/group labels and locally derived category aggregates only |
| Local state | `/opt/actual/insights-data/insights.sqlite` |
| Decrypted cache | per-run `/tmp` directory on container tmpfs; always destroyed |
| Authentication | exact operator `Tailscale-User-Login` through Tailscale Serve |
| Backup | inherited encrypted PBS image for VM 127 |

## Exactly what leaves VM 127

The request contains the completed target month, currency code, a synthetic category reference,
category group/name, income/expense type, target budgeted/actual/balance integer-cent amounts,
available-history count, previous-month actual, prior three/twelve-month category averages,
target-versus-three-month basis points, and budget variance.

Category and group names are sent verbatim. No Actual identifier is sent. The request contains no
transactions, payees, accounts, notes, imported descriptions, rules, schedules, tags, budget name,
Sync ID, credential, raw database, net worth, or account balance. Historical budget months are read
locally only to calculate category averages.

OpenAI states that API input is not used for training by default, but ordinary API requests may be
retained in abuse-monitoring logs for up to 30 days. `store: false` disables Responses application
state; it does not grant Zero Data Retention. If category-level disclosure is not acceptable, leave
`actual_insights_enabled: false`.

## Enable

1. Create a dedicated OpenAI project and project-scoped API key. Configure a conservative project
   spend limit and alerts. Do not reuse a personal or broad automation key.
2. In Actual, copy the Sync ID from advanced settings. Retrieve the server and separate E2EE
   passwords from Vaultwarden without displaying them in terminal history.
3. On mgmt-vm, create the four paths configured by:
   `actual_insights_server_password_file`, `actual_insights_sync_id_file`,
   `actual_insights_e2ee_password_file`, and `actual_insights_openai_api_key_file`. Each file contains
   one value and must be mode `0600`. Never commit or place them under the repository.
4. In the real gitignored `inventory/group_vars/all.yml`, set the exact Tailscale login and opt in:

   ```yaml
   actual_insights_operator_login: YOUR_TAILSCALE_LOGIN
   actual_insights_currency: AUD
   actual_insights_timezone: Australia/Adelaide
   actual_insights_enabled: true
   ```

5. Run the application tests and dependency audit from `apps/actual-insights`, then deploy from
   `ansible/`:

   ```bash
   npm test
   npm audit --omit=dev
   ansible-playbook playbooks/provision-actual.yml
   ```

The playbook builds the local companion image, stages mode-`0400` read-only secret mounts, retains
Actual at the root URL, adds `/insights` to the existing Tailscale Serve listener, and verifies both
loopback ports. Deploying does not call the model; only the UI button does.

## First live acceptance

Before treating the overlay as available:

1. Confirm `docker compose ps` shows both containers healthy.
2. Confirm `ss -tlnp` shows ports 5006 and 5007 only on `127.0.0.1`.
3. Confirm `/insights` returns `403` without a Tailscale identity and opens for the configured operator.
4. Close and sync a non-sensitive completed month in Actual, then generate its memo manually.
5. Inspect the stored snapshot using a local SQLite/JSON view and confirm it matches the allowlist
   above. Specifically search for known account and payee labels and confirm they are absent.
6. Confirm model prose contains no numeric claims and that exact evidence amounts are rendered by the
   local UI.
7. Confirm `/tmp` inside the container has no retained Actual budget directory after the request.
8. Run `npm audit --omit=dev` again if the image was built from a refreshed lockfile.

This repository cannot perform the live checks because the private VM and credentials are outside
the agent's network boundary.

## Monthly workflow

1. Finish reconciliation and categorization in Actual for the previous month and let Actual sync.
2. Open `/insights` from an operator device.
3. Select the completed month and click **Generate monthly memo** once.
4. Review the category evidence in Actual before acting. The memo is an observation layer, not
   financial advice and not an automatic budget edit.

The application refuses the current or a future month and rejects concurrent generation. Repeating a
completed month creates another audit record, which is useful after category corrections.

## Operations

- Health inside VM 127: `curl -fsS http://127.0.0.1:5007/healthz`
- Container state: `cd /opt/actual && sudo docker compose ps insights`
- Redacted application logs: `cd /opt/actual && sudo docker compose logs --tail=100 insights`
- Tailscale routing: `sudo tailscale serve status`
- Local database: `/opt/actual/insights-data/insights.sqlite` (mode `0600`)

Application errors deliberately omit upstream details because Actual and model errors can contain
sensitive context. Diagnose credentials by checking file existence/mode and rotating the individual
secret rather than enabling verbose logs.

To disable, set `actual_insights_enabled: false` and rerun the playbook. The container is removed as
an orphan, but the SQLite audit and secret files are retained deliberately. Remove the `/insights`
Serve route manually if disabling for an extended period. Do not delete state or credentials as part
of an ordinary disable operation.

## Upgrade and recovery

- Keep `@actual-app/api` exactly aligned with `actual_image` before upgrading Actual.
- Review Actual and OpenAI release notes, run tests/audit, then rebuild during the maintenance window.
- Preserve the `adm-zip: 0.6.0` security override until upstream Actual resolves to an equal or newer
  patched release; do not downgrade it to satisfy an automated package suggestion.
- The model pin is a deliberate behavior contract. Evaluate prompt/schema behavior with category-only
  fixtures before changing it.
- VM 127's encrypted PBS image includes the SQLite audit database and VM-local secret files. The
  existing isolated VM restore procedure applies. The Actual API cache is intentionally unrecoverable
  because it exists only on tmpfs during a request.

Related: ADR-024, ADR-023, ADR-018, and `docs/components/actual-budget.md`.
